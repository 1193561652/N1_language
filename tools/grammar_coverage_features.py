"""Explicit grammar-point normalization for the coverage model.

Rules search reviewed construction annotations, not whole passages or wrong
answer options. Families indicate related functions, never full equivalence.
"""
import re,unicodedata

# id | related-function family | construction regex
RULE_TEXT=r'''
negative_emphasis|negative_emphasis|いっさい|一切|なんら|何ら|まるで.{0,8}ない|とても.{0,5}ない|一向に.{0,5}ない
only_shika|limitation|しか.{1,12}(?:ない|知ら|言いよう)
ni_suginai|limitation|にすぎ|に過ぎ
de_shikanai|limitation|でしかな
nominarazu|addition|のみならず
ue_ni|addition|うえに|上に
katSU|addition|かつ
naradeha|exclusive_quality|ならでは
atte_no|necessary_basis|あっての
naku_shite|necessary_basis|なくして
nai_kotoniha|necessary_basis|ないことには
nakutehanaranai|obligation|なくてはならない|なければならない|なきゃいけない
nara_madashimo|contrast_exception|ならまだしも|ならともかく
tohaie|concession_connector|とはいえ
nagara_mo|concession|ながらも
tsutsu_mo|concession|つつも
monono|concession|ものの
ni_shiro|concession|にしろ|にせよ|にしても
ni_shiteha|contrary_expectation|にしては
taha_iiga|contrary_expectation|たはいいが
kato_omoikiya|contrary_expectation|かと思いきや
so_kato_omoeba|contrast|そうかと思えば
hannmen|contrast|反面
ippou|contrast_connector|一方
nanoni|contrary_expectation|なのに
nimokakawarazu|concession_connector|にもかかわらず
noni_regret|regret_reproach|だろうに|よかったのに|いいものを|^ものを$
darouto_darouto|unconditional_concession|だろうと|であろうと|だろうが|はどうであれ|どんなに.{0,4}ても|いくら.{0,4}からといって
you_tomo|unconditional_concession|ようとも|ようと下がろうと
kara_toitte|reject_sufficient_condition|からといって
baii_toiu_monodehanai|reject_sufficient_condition|ばいいというものではない|ばいいかというと|かといえばそうではなく|からといってより
sAE_condition|sufficient_condition|さえしなければ|さえ.{0,8}ば
kagiri_condition|continuing_condition|いる限り|いるかぎり|働けるかぎり|ない限り
kara_niha|commitment_condition|からには
ijou_reason|commitment_condition|以上
to_nareba|situational_condition|ともなれば|となると
to_sureba|hypothetical_condition|とすれば|としたとして|したとして
shidai_de|depending_condition|次第で|次第では|次第で決まる
mononara|difficult_hypothesis|ものなら
de_aru_nara|hypothetical_condition|んなら|んだったら|ないとすれば
ni_kagitte|exception_timing|に限って
ba_koso|necessary_basis|ばこそ|てこそ
ki_ni|occasion_start|を機に
wo_kawakiri|sequence_start|を皮切り
ni_sakidachi|before_action|に先立
wo_hikaete|before_action|を控え
wo_motte|boundary_or_means|をもって
wo_saigoni|end_boundary|を最後に
uchi_ni|during_change|うちに
uchi_kara|before_action|うちから
ru_nari|immediate_sequence|るなり
totan|immediate_sequence|とたん
to_omottara|immediate_sequence|と思ったら
te_kara_toiu_mono|persistent_change|てからというもの
ni_tsuke|repeated_trigger|につけ
teha_repeat|repeated_action|^Vては$|描いては直す
tari_tari|enumeration|たり.{0,15}たり
hi_mo_areba|enumeration|日もあれば|するもしないも|売れるも売れないも
to_aimatte|joint_cause|と相まって
ni_tomonatte|accompanying_change|にともなって|に伴って
to_hikikaeni|exchange|と引きかえに
wo_ukete|background_cause|を受けて
koto_kara|evidential_cause|ことから
koto_mo_atte|additional_cause|こともあって
to_atte|special_cause|とあって
yueni|formal_cause|ゆえに|ゆえの
dake_atte|expected_cause|だけあって
dake_ni|expected_cause|だけに
bakari_ni|adverse_cause|ばかりに
sei_ka|adverse_cause|せいか|せいで
amari_cause|excess_cause|あまり
koto_dakara|expected_cause|ことだから
shidai_desu|explanatory_cause|次第です
nonowo_iikotoni|opportunistic_cause|のをいいことに
ni_yoru_tokoro|contribution_cause|によるところが大きい
beku|purpose|べく
tameniha|purpose_condition|ためには
kotoni_yotte|means|ことによって|ことで
ni_to|purpose|おみやげにと
you_ni|purpose|ことのないように|できるように
ni_oite|domain|において|における
to_shite|role_standard|として|としながら|とするには
ni_totte|viewpoint_standard|にとって
kara_shite|viewpoint_standard|からして
ni_shitemireba|viewpoint_standard|にしてみれば
kara_sureba|viewpoint_standard|からすれば|から言わせてもらえば
to_itashimashiteha|viewpoint_standard|といたしましては
ni_kaketeha|domain|にかけては
kagiri_knowledge|knowledge_boundary|知る限り
wo_yosoni|disregard|をよそに
katomokaku|set_aside|はともかく
gotoshi|comparison_appearance|かのごとく|がごとく|ごとき
you_na_simile|comparison_appearance|かのよう|ような意味|ような状態|ようでもある
mitai|comparison_appearance|みたい
youda_inference|evidential_inference|どうやら.{0,4}ようだ
sou_ni_nai|negative_prospect|そうにない|そうになかった
sou_ni_naru|imminent_state|そうになる
sou_da_hearsay|hearsay|そうだ|だとか
toiu_hearsay|hearsay|という\(传闻\)|多いというのが
mikomi|forecast|見込み
kamoshirenai|possibility|かもしれない
kane_nai|adverse_possibility|かねない
osore|adverse_possibility|恐れ|おそれ
ni_chigainai|strong_inference|に違いない
ni_kimatteiru|strong_assertion|に決まっている
hazu|expectation|はず
to_omowareru|evidential_inference|と思われる|と見られて
to_ierudarouka|rhetorical_doubt|といえるだろうか|そうだろうか|なのだろうか
hatashite|rhetorical_doubt|はたして|果たして
ka_douka|embedded_alternative|かどうか|か否か
you_to_suru|attempt_intention|ようとした|ようとする|ようとはしな|つかもうと|しようとした|しようとする
you_toshiteiru|imminent_completion|ようとしている
tsumori|intention_or_belief|つもり
you_to_purpose|volitional_quote|しようと$|見ようという|伝えようと|てもらおうと
te_miseru|demonstration_intention|てみせ|ってみせ
to_suru_ka|decision|とするか
te_hoshii|desire_other|てほしい|いってほしい|やめてほしい
tagaru|third_person_desire|たがる
tai|desire_self|いたいです|たいところ|たかったもの
koto_ni_suru|decision|ことにして|ことにする|ことと致します
koto_ni_naru|result_or_decision|ことにな|こととな
you_ni_naru|ability_change|ようになる
made_ni_naru|degree_change|までになった|までに至らない
tsutsu_aru|ongoing_change|つつある
te_shimau|completion_regret|てしま|でしま|じゃわ
te_oku|preparation_state|ておい|といて|ておけ|っておく
te_miru|trial|てみな|てみる
ta_kotogaaru|past_experience|たことがある|働いたことがない
ppanashi|left_state|っぱなし
ta_tsumori|completed_belief|したつもり|洗ったつもり
ta_monoda|past_reminiscence|たかったものだ|たものだ
mama|unchanged_state|まま
te_iru|ongoing_state|している|していた|ていた|いなければ|していない|ずにいた
te_kuru|direction_toward_now|てきた|てくる|てきましょう|でくる
te_iku|direction_future|ていく|ていこう|ていって|てまいり|て参り
te_itadaku|benefactive_receive|いただ|頂戴|てもら|でもら
te_kureru|benefactive_give|てくれ|でくれ|てくださいました
te_ageru|benefactive_give_out|てやる|てもらってやって|もらってやって
honorific_sonkei|honorific_sonkei|おいで|ご覧にな|おっしゃ|なさい|お越し|見えました
honorific_humble|honorific_humble|存じ|申し上げ|お届けに上が|お迎えにあが|お出し|いたしかね|てまいり
honorific_request|honorific_request|願い|願え|くださいませんか|いただけると助かる
tekudasai|reader_or_listener_request|てください|思って頂きたい
passive|passive|悩まされ|誘われ|勧められ|受け入れられ|知らされ|刺され|揺られ|任され|失われ|助けられ|親しまれ|言われる|認められて
causative_passive|causative_passive|させられ|思わされ
causative|causative|泣かせ|終わらせ|思わせ|咲かせ|失わせ|待たせ|気づかせ|やらせ|見させ
sasete_morau|causative_permission|させてもら|かせていただ
zu_ni_sumu|avoid_action|ずに済|なくて済
zu_ni|negative_accompaniment|ずに|ないで
koto_naku|negative_accompaniment|ことなく|ことなしに
gatai|psychological_difficulty|がたい
kane_ru|polite_inability|かねます
youganai|no_means|ようがない|ようもない|ようのない
kireru|completion_ability|きれない|きれなく|きれっこ|きりな
teha_irarenai|situational_inability|てはいられない|てばかりもいられない
dokorodehanai|situational_inability|どころではな
wakenihaikanai|social_constraint|わけにはい|わけにもい
double_negative|qualified_affirmation|しないでもない|なくもない|なくはなかった|ないことはない
naitomokagiranai|negative_possibility|ないともかぎらない
kagiranai|non_absolute|とは限らない
wakedehanai|partial_negation|わけじゃない|わけではない
wakeganai|impossibility_assertion|わけがない
monoka|strong_rejection|ものか|もんか
shika_nai|only_choice|しかない|しかあるまい
ni_koshita|best_option|に越したことはない
mademonai|unnecessary|までもない
beki|normative_advice|べき
tehanaranai|prohibition|てはならない
njanakatta|regret|んじゃなかった
shikatanai|inevitable|しかたがない
nimohodogaaru|excess_evaluation|にもほどがある
kiwamarinai|extreme_evaluation|極まりない
toittaranai|extreme_evaluation|といったらない
kotoka|exclamation|ことか
sonomono|extreme_evaluation|そのもの
te_naranai|spontaneous_emotion|てならない
te_made|extreme_action|てまで|ってまで
made_ni|extreme_degree|までに
monja_nai|extreme_evaluation|なんてもんじゃない
ni_shite|stage_emphasis|にして初めて|枚目にして|^にして$
koso|contrast_emphasis|こそ.{0,8}が|こそしなかった
ima_de_koso|past_present_contrast|今でこそ
n_mo_n_nara|parallel_reproach|NもNなら
n_mo_n|parallel_reproach|君も君だ
ha_suru|contrast_affirmation|はする|はしない|読みもしない
dakeno_koto|minimization|だけのこと
hodo_dehanai|degree_limit|ほどではない|ほどのことではない
kurai_nara|prefer_alternative|くらいなら
toitta_tokoro|approximate_degree|といったところ
kotomo_nai|unnecessary|ことはない
darou|modal_judgment|でしょう|だろう
nodearu|explanatory_modality|(?<!も)のである|(?<!も)のだ|(?<!も)のです|なのです|なんだ|んだもん
koto_da_explain|explanatory_definition|ということだ|というものである|というわけ
tte_quote|colloquial_quote|だってこと|っていう|なんて気持ち|なんて思|ったって
toiu_noun|quote_noun|という気持ち|という自覚|との問い合わせ|との報告|という危機感|というような|といった症状
toiu_yori|reformulation|というより
dakke|recall_question|だっけ
janai_ka|confirmation_or_reproach|じゃないか|ではないか|じゃない
tokoro_datta|near_miss|ところだった|ところでした
ageku|adverse_result|あげく
shimatsu|adverse_result|始末
sue_ni|eventual_result|末に
beki_tokorowo|contrary_expectation|べきところを
nagara_ni_shite|state_with_result|ながらにして
ue_de|prior_action|上で|うえで
tsuide|incidental_action|ついで
ni_sotte|following_standard|に沿って
fumae|consideration_basis|踏まえ
ni_kansuru|topic_modifier|に関する
wo_taishoni|target_scope|を対象に
taeru|worthiness|にたえる
hi_ni|comparison|比べ物にならない|遠く及ばない
ni_kakatteiru|dependency|にかかっている
ni_yugeshiku|compelled_action|余儀なく
naraba|hypothetical_condition|(?<!なぜ)ならば|利用すれば|承知していれば|いれば$|しなければ$|片付けなくても
tokorode|ongoing_event|したところ|たところ|ところを
tsuzukeru|continuation|続ける
gachi|tendency|がち
gaaru|partial_trait|ところがある
to_omou|reported_thought|と思う|と思った|と思って|と思える
node|cause_connector|んだから|からでもあります|からだが
sokode|problem_solution_connector|そこで
sonokekka|result_connector|その結果
sonotame|cause_reference|そのため
nazenara|reason_connector|なぜなら
soshite|addition_connector|そして
suruto|sequence_connector|すると
sonouede|sequence_connector|その上で
sunawachi|reformulation_connector|すなわち
tada|limitation_connector|^ただ$
tokoroga|contrary_connector|ところが
souiえば|topic_recall_connector|そういえば
mazu|sequence_connector|^まず$
tachikani|acknowledge_then_contrast|たしかに
kou_shite|deictic_method|こうして
so_shita|anaphora_class|そうした|こうした|そういう|そんな
sono|anaphora_specific|その時|そのため|それに|それが|それを|小説でもそうだ
kono|deixis_current|この箱|あの若者|あれ以来
itsukoro|temporal_question|いつごろ
tojitsu|temporal_reference|当時|ある日|あるとき
ni_toshi|benefactive_perspective|君から借りた|貸したまま
nii|author_identity|自分がもう一人|自作评价与自谦否定
ni_suru_mono|general_rule|失敗するもの|たがるもの
taikoto|rhetorical_evaluation|じゃあねはないだろう
iya|negative_assertion|父ではない|否定できなくなる
hyoka|author_evaluation|逃避でしょう|たくましく思えます|ひどいやつ
ippan_denial|partial_negation|それだけが.{0,4}ではありません
kindef|explanatory_definition|一生の仕事とは
syudan|means|会って話すことで
imasu|general_explanation|示すのです
watashi|viewpoint_standard|わたしにとって
zu_ni_ita|negative_continuing_state|できずにいた|買えずにいた
kata|method_nominal|使いよう|書き方
da_ni|parallel_enumeration|に、にと|Tシャツにジーンズ
mo_kouhan|degree_emphasis|40代も後半
no_kiwami|evaluation_collocation|身が引き締まる思い|不快な思いをした
hokori|evaluation_collocation|誇りに思う
dou_した|deliberation|どうしたものか
ikura|degree_emphasis|何の説明にも|少なからぬ
akumade|limitation|だけでも
amari_mo|contrast|大人は大人で|それはそれで|あったらあったで
ni_atte|situational_background|にあって
dake_muda|futility_evaluation|だけ無駄
nanka|self_deprecating_example|なんか
wo_mo|case_emphasis|をも$
nozoite|exception_exclusion|場合を除いて
tte_monda|strong_assertion|ってもんだ
negative_so|negative_emphasis|そう簡単には直らない
demo_arumai|inappropriate_action|でもあるまい
tokade|hearsay_cause|とかで
nakanaka|positive_evaluation|なかなか
you_nimo|situational_inability|こうにも
nanimo_nakutemo|unnecessary|なにも怒らなくても
nai_mademo|concession|ないまでも
inamenai|acknowledgement|ことは否めない
bakari_tonaru|final_stage|ばかりとなった
mottomo|limitation_connector|もっとも
teha_komaru|adverse_condition|ては困る
masuyouni|wish|ますように|ませんように
deii_kara|minimal_condition_request|でいいから
temo_hajimaranai|futility_evaluation|ても始まらない
spontaneous_reru|spontaneous|思い出される|^思われる$
tekaradeha|too_late_condition|てからでは
monoda_exclamation|exclamation|作れるものだ
ntoiun|universal_emphasis|花という花
ka_naika|temporal_boundary|か入らないか
kagondehanai|strong_assertion|過言ではない
iwaseruto|viewpoint_standard|言わせると
tameniomou|benefit_motive|ためを思って
toimashouka|tentative_wording|といいましょうか
zaru|archaic_negative|ざる
mazumachigainai|strong_inference|まず間違いない
arumai_shi|negative_premise|あるまいし
kurai_degree|degree|くらい|ぐらい|ほど
saru_kotonagara|addition|もさることながら
toiu_tokorode|stage_description|というところで
kotoni_taishi|response_target|ことに対し
tenokotoda|explanatory_cause|てのことだ
vni_vrenai|situational_inability|やめるにやめられず
oyobi|noun_coordination|及び
sura|extreme_example|すら
datte_example|illustration|ピアスだって|私だって
moshikashitara|hypothetical_possibility|もしかしたら
no_kotoda|topic_introduction|トイレのことだ
tara_na|wish|いたらなあ
dearu|plain_assertion|^である$|力である
toieru|evaluation_conclusion|一冊といえる
nagara_child|concessive_state|子供ながら
mo_additive|addition|牛も
tatteii|permission|いたっていい
toittemo|limitation_discourse|といっても
mashouka|invitation|しましょうか
denofusoku|insufficiency_condition|半日では足りない
kotolist|nominalized_instruction|^こと$
subject_reference|subject_reference|^彼$
generic_noun|generic_reference|犬の礼儀作法
equal_relation|reformulation|対等の関係
betunokao|contrast_viewpoint|別の顔
taikokutono|ongoing_generic|聞いてます|^励ます$|よく思う
pastexperience|temporal_past|見つけられなかった|聞くだけだった|助かった
quoted_speech|direct_quotation|嬉しそうにこういった
ellipsis_command|elliptical_instruction|消すように
ellipsis_cause|elliptical_cause|^思って$
subject_ellipsis|subject_ellipsis|母親に会いたくなって
ga_contrast|contrast_connector|^が$
temo_concession|concession|会うので|残っていても|反論したくなっても
quote_refutation|concession|聞こえはいいが
quote_noun_extended|quote_noun|という何かしらの
nominal_predicate_modifier|nominal_modifier|存在であるコンビニ
resistance_case|case_dependency|抵抗がある人
no_ka|embedded_question|何だったのか|のかと|ことが.{0,3}のか|何であって|のかも
no_ha|nominalized_topic|のは|のも|のが
koto_wo|nominalized_object|ことを|ことが
'''

RULES=[]
for line in RULE_TEXT.strip().splitlines():
    ident,family,pattern=line.split('|',2)
    RULES.append((ident,family,re.compile(pattern)))

# The grammatical role, not merely the ending, resolves ambiguous constructions.
SEMANTIC_RULES=[
 ('past_recall','temporal_past',r'回忆|过去时|过去经历|当时|过去愿望'),
 ('generic_present','temporal_generic',r'一般习性|非过去|常态|普遍现象|普遍规则|一般.{0,8}倾向|一般感受'),
 ('counterfactual','counterfactual',r'反事实|本应|假设早知'),
 ('quotation_content','quotation',r'引用内容|引用完整|引用判断|引用补出|引用修饰|引用与'),
 ('relative_clause','relative_clause',r'关系从句|小句修饰|名词修饰|修饰名词|修饰コンビニ|修饰店舗|修饰もの|修饰経緯'),
 ('embedded_question','embedded_question',r'嵌入疑问'),
 ('nominalization','nominalization',r'名词化'),
 ('quote_noun','quote_noun',r'引用修饰|引用.{0,8}修饰|との引用'),
 ('multiple_modifiers','multiple_modifiers',r'两层名词修饰|两层主题|分层'),
 ('adverbial_blocks','adverbial_dependency',r'各成块|宾语、手段|副词.*修饰|程度各'),
 ('case_dependency','case_dependency',r'助词.{0,8}搭配|宾语|が标记|内部主语|对象与'),
 ('sequence_blocks','sequence',r'先后句块|实际顺序|之后接|前后动作主体'),
 ('reader_request','reader_request',r'请求读者|问读者|读者回想'),
 ('author_evaluation','author_evaluation',r'作者评价|自己的积极评价|作者.*评价|自我思考|自谦'),
 ('author_stance','author_stance',r'全文立场|作者.*立场|作者.*原则|自己的愿望'),
 ('discourse_summary','summary',r'归纳|总结|概括|定义|同义解释'),
 ('discourse_example','illustration',r'举.*例|举例|以.*例子'),
 ('discourse_cause','causal_discourse',r'补充原因|解释为何|以此解释|引出.*原因'),
 ('discourse_solution','problem_solution',r'应对办法|应对措施|提出.*办法'),
 ('discourse_limitation','limitation_discourse',r'限制说明|先承认.*再|先说明.*再|不能涵盖'),
 ('discourse_contrast','contrast_discourse',r'转向|逆接|转入|反转|对比|对照'),
 ('discourse_reference','reference',r'回指|回扣|指前一句|指前述'),
 ('subject_viewpoint','subject_viewpoint',r'动作主体|视角|受.*一方|受益|授受对象'),
 ('register_consistency','register',r'说明文语气|书面说明|自我思考语气|维持.*语气'),
 ('rhetorical_reproach','rhetorical_reproach',r'反语|责备|遗憾'),
 ('volitional_intention','intention',r'意志|意图|决定今后|未来计划'),
 ('spontaneous','spontaneous',r'自发|不由自主'),
 ('prohibition','prohibition',r'不允许|禁止'),
 ('prerequisite','necessary_basis',r'必要条件|不可缺少|才构成|所需步骤|所需条件'),
 ('weak_affirmation','qualified_affirmation',r'弱肯定|双重否定|并非不能'),
]

def normalized(s):
    s=unicodedata.normalize('NFKC',s)
    s=re.sub(r'[～~\s／/…＋+（）()、,。]','',s)
    return s

def features(row):
    text=unicodedata.normalize('NFKC',row['construction']).replace('~','')
    evidence=re.split(r'不是|而非|区别|不能只|非传闻|不作',row['evidence'])[0]
    found={}
    spans=[]
    for ident,family,rule in RULES:
        matches=list(rule.finditer(text))
        if not matches:continue
        spans.append((ident,family,matches))
    # Avoid awarding separate credit for a short grammatical piece swallowed
    # by a more informative fixed expression.
    for ident,family,matches in spans:
        valid=[m for m in matches if not any(m.start()>=n.start() and m.end()<=n.end() and len(n.group())>len(m.group()) for other,_,ms in spans if other!=ident for n in ms)]
        if valid:found['form:'+ident]={'family':family,'source':'construction','evidence':[m.group() for m in valid],'weight':1.0}
    for ident,family,pat in SEMANTIC_RULES:
        m=re.search(pat,evidence)
        if m:found['role:'+ident]={'family':family,'source':'annotation_evidence','evidence':[m.group()],'weight':0.65}
    # Same written ending, different tested function: never conflate these.
    if 'form:ta_monoda' in found and re.search('反语|责备|感叹',row['evidence']):
        found.pop('form:ta_monoda')
        found['form:monoda_reproach']={'family':'rhetorical_reproach','source':'annotation_evidence','evidence':[row['evidence']],'weight':1.0}
    if 'form:tsumori' in found:
        family='completed_belief' if re.search('已经|已做|自认|仿佛已经|主观认定',row['evidence']) else 'intention_or_belief'
        found['form:tsumori']['family']=family
    if 'form:ue_de' in found and '語るうえで' in text:
        old=found.pop('form:ue_de');old['family']='domain'
        found['form:ue_de_domain']=old
    if 'form:to_shite' in found:
        if re.search('立场|身份',row['evidence']):
            old=found.pop('form:to_shite');old['family']='viewpoint_standard'
            found['form:to_shite_standpoint']=old
        elif re.search('とするには|題材とし',text):
            old=found.pop('form:to_shite');old['family']='object_predication'
            found['form:to_suru_object']=old
    # A nominal-predicate modifier is a concrete sorting construction.
    if row['problemNumber']==6 and 'form:nominal_predicate_modifier' in found:
        found['role:relative_clause']={'family':'relative_clause','source':'annotation_evidence','evidence':[row['evidence']],'weight':0.65}
    # A family of related surface expressions is not an exact repeat.
    split_patterns={
      'negative_emphasis':[(r'いっさい|一切','issai'),(r'なんら|何ら','nanra'),(r'とても','totemo'),(r'まるで','marude'),(r'一向','ikkou')],
      'darouto_darouto':[(r'であろうと','dearouto'),(r'だろうと','darouto'),(r'だろうが','darouga'),(r'どうであれ','doudeare'),(r'どんなに','donnanitemo'),(r'いくら','ikurakaratoitte')],
      'honorific_sonkei':[(r'おいで','oide'),(r'ご覧','goran'),(r'おっしゃ','ossharu'),(r'なさい','nasaru'),(r'お越し','okoshi'),(r'見えました','mieru')],
      'honorific_humble':[(r'存じ','zonjiru'),(r'申し上げ','moushiageru'),(r'上が|あが','agaru'),(r'お出し','odasu'),(r'いたし','itasu'),(r'まいり|参り','mairu')],
      'te_itadaku':[(r'いただ','itadaku'),(r'頂戴','choudai'),(r'もら','morau')],
      'te_kureru':[(r'ください','kudasaru'),(r'くれ','kureru')],
    }
    for ident,patterns in split_patterns.items():
        old=found.pop('form:'+ident,None)
        if not old:continue
        matching=' '.join(old['evidence'])
        added=False
        for pat,suffix in patterns:
            if re.search(pat,matching):
                found['form:'+ident+':'+suffix]=old.copy();added=True
        if not added:found['form:'+ident]=old
    # Chapter labels are a weak fallback; not detailed grammar equivalence.
    # Always retain an unmatched construction so that generic skills cannot
    # alone make an unrecognized pattern appear fully covered.
    if not any(k.startswith('form:') for k in found):
        found['unresolved:'+normalized(text)]={'family':None,'source':'unresolved_construction','evidence':[text],'weight':1.0}
    return found
