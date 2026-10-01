import pathlib,json,re,math
P=pathlib.Path(__file__).resolve().parents[1];O=P/'11 Learning Analytics/references';p=O/'kanji-reading-word-families.json';J=json.loads(p.read_text('utf-8'));D=json.loads((P/'offline-exam-tool/data.js').read_text('utf-8-sig').split('=',1)[1].rstrip(';\n '))
# Commonness is a transparent teaching prior, NOT a measured Japanese-language frequency.
# 3: everyday anchor; 2: general formal/written word; 1: limited/specialized anchor.
spec='''正|せい:3:厳正,正確;しょう:3:正直;ただしい:3:正しい
厳|げん:2:厳正;きびしい:3:厳しい
凝|ぎょう:2:凝縮,凝視
縮|しゅく:2:凝縮,縮小
自|じ:3:自粛;し:3:自然;みずから:2:自ら
踏|とう:2:踏襲,雑踏
群|ぐん:2:群衆,抜群
越|えつ:2:卓越;こえる:3:越える
趣|しゅ:3:趣旨,趣味
政|せい:3:行政,政治,政策
行|こう:3:遂行,旅行,銀行,行動;ぎょう:2:行政
合|ごう:2:合意;がっ:2:合併,合致;あい:3:試合,場合
執|しゅう:2:執着;しつ／しっ:2:執筆,固執
着|ちゃく:3:執着,定着;きる:3:着る;つく:3:着く
興|こう:2:興奮,復興,振興;きょう:3:興味
奮|ふん:2:興奮,奮闘
復|ふく:3:復習;ふっ:2:復興,復旧
露|ろ:2:暴露,露骨,露出;ろう:2:披露
筋|すじ:3:本筋,筋道;きん:3:筋肉
図|ず:3:指図,地図;と:3:図書館;はかる:2:図る
派|は:2:派生,派遣;ぱ:3:立派
生|せい:3:派生;しょう:2:生じる;じょう:3:誕生;うまれる:3:生まれる
画|かく:3:画一的,計画;が:3:画面
人|じん:3:人脈;にん:3:人間
手|て:3:手薄,手際,手軽;しゅ:3:手段,選手
心|しん:3:心配;じん:2:肝心;こころ:3:心遣い;ここち（整词）:3:心地よい
相|そう:2:相場,相互;あい:3:相手
大|だい:3:膨大,大臣;たい:3:大切
盛|じょう:2:繁盛;せい:2:盛大
日|にち:3:日夜,日時;じつ:3:休日
時|じ:3:随時,時間,日時
潜|せん:2:潜伏,潜在;ひそむ:2:潜んで
粘|ねん:2:粘膜;ねばる:2:粘って
促|そく:2:督促;うながす:2:促した
跡|せき:2:軌跡;あと:3:跡地
地|ち:3:跡地,心地よい,地図
健|けん:3:健康,健全;すこやか:2:健やか
軽|けい:2:軽率,軽減;かる（がる）:3:手軽
忠|ちゅう:2:忠告,忠実
告|こく:3:忠告,告白
名|めい:3:名誉,名称
鈍|どん:2:鈍感;にぶい／にぶる:3:鈍い,鈍って
沈|ちん:2:沈下,沈黙;しずむ:3:沈む
崩・壊|ほう・かい（音读）:2:崩壊;くずれる（崩）:3:崩れやすい;こわす（壊）:3:壊されて
閲|えつ:2:閲覧,検閲
明|めい:2:釈明,克明
克|こく:2:克明,克服
督|とく:2:督促,監督
承|しょう:2:承諾,了承
中|ちゅう:3:中枢,胸中
繁|はん:2:繁盛,繁殖
然|ぜん:2:漠然,騒然
約|やく:3:契約,誓約書
華|はな／ばな:2:華々しく,華やか
潤|うるおう／うるおす:2:潤って,潤す
憤|いきどおる:2:憤り,憤った
臨|のぞむ:2:臨む,臨みたい
慕|したう:2:慕われる,慕って
偏|かたよる:2:偏って,偏り
戒|いましめる:2:戒める,戒めたい
樹・木|じゅ・もく（音读）:2:樹木,樹立,木材'''
mapping={}
for l in spec.splitlines():
 c,v=l.split('|');mapping[c]=[dict(reading=b.split(':')[0],commonness=int(b.split(':')[1]),words=b.split(':')[2].split(',')) for b in v.split(';')]
targets=J['targets']; allwords={w for bs in mapping.values() for b in bs for w in b['words']};coverage={w:set() for w in allwords};occ={w:set() for w in allwords}
for year,e in D['exams'].items():
 for cat,qs in e.items():
  if cat=='文字' or not isinstance(qs,list):continue
  for q in qs:
   if not isinstance(q,dict):continue
   txt='\n'.join(str(q.get(k,'')) for k in ['question','passage','subQuestion'])+'\n'+'\n'.join(q.get('options',[]))
   txt=re.sub(r'⟦/?u⟧|【|】|</?u>','',txt)
   for w in allwords:
    if w in txt:coverage[w].add(year);occ[w].add((year,cat,str(q.get('id') or q.get('number'))))
wrong=set('厳正 凝縮 自粛 踏襲 丘陵 卓越 兆し 猛烈 管轄 群衆 執着 合併 趣旨 興奮 行政'.split())
output=[]
for f in J['coreFamilies']:
 bs=mapping[f['character']]
 assert set(w for b in bs for w in b['words'])==set(f['targets']+f['related']),f['character']
 for b in bs:
  b['targetQuestionCount']=sum(t['target'] in b['words'] for t in targets)
  b['crossSubjectPaperCount']=len(set().union(*(coverage[w] for w in b['words'])))
  b['crossSubjectQuestionCount']=len(set().union(*(occ[w] for w in b['words'])))
  b['recentWrongWords']=sorted(wrong.intersection(b['words']))
 totals={k:sum(b[k] for b in bs) for k in ['targetQuestionCount','crossSubjectPaperCount','commonness']}
 for b in bs:
  # Cross-subject absence means no within-list evidence, not that the reading is rare.
  t=b['targetQuestionCount']/totals['targetQuestionCount'] if totals['targetQuestionCount'] else 1/len(bs)
  e=b['crossSubjectPaperCount']/totals['crossSubjectPaperCount'] if totals['crossSubjectPaperCount'] else 1/len(bs)
  c=b['commonness']/totals['commonness']
  b['rawWeight']=.60*t+.25*e+.15*c
  b['weightPercent']=math.floor(b['rawWeight']*100)
 rem=100-sum(b['weightPercent'] for b in bs)
 for b in sorted(bs,key=lambda b:b['rawWeight']*100-b['weightPercent'],reverse=True)[:rem]:b['weightPercent']+=1
 assert sum(b['weightPercent'] for b in bs)==100
 output.append(dict(character=f['character'],branches=bs))
J['readingWeights']=dict(meaning='within-family study allocation, not probability of future JLPT occurrence or general Japanese use',formula=dict(targetQuestionShare=.60,crossSubjectPaperShare=.25,manualCommonnessShare=.15),commonnessScale={'3':'日常／基础表达可作为熟词锚点（教学判断）','2':'通用书面／正式词汇（教学判断）','1':'较专门／较少用的锚点（本表未使用）'},matching='精确字面串，跨科目每期至多计一次；只计各分支列出的代表词，未穷举该字所有词。关联词有原文证据，但统计不证明某次出现就考该读音。',variantPolicy='固執默认用常见こしつ分支计数，こしゅう读法合法但未二次累计同一字面词。',families=output)
p.write_text(json.dumps(J,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
L=['# 汉字读音：频率、常用程度与复习权重','','对应[词族学习册](kanji-reading-word-families.md)。覆盖其中61组核心词族的全部读音分支；271字的完整索引仍在学习册内，未给没有足够分支定义的字制造精确权重。','','## 如何理解权重','','**每组内部合计100%，用于分配该组的复习注意力，不是日语使用频率，也不是下次考试命中率。不同汉字之间的100%不能直接比较。** 单一分支的100%仅表示本表该组只列一种，不表示这个字只有一种读法。','','默认公式：60% × 主读音题次数占比＋25% × 跨科目代表词覆盖期次占比＋15% × 常用程度评分占比。该配比是为本次读音备考设定的教学参数，未经过预测验证。','','- 主题次数：31期186道读音题中的目标词次数，同一词不同期次各计一次。','- 跨科目题数：代表词在词汇、语法、阅读、听力中的题目数；仅展示，不直接用于加权，避免长篇与重复材料放大。','- 跨科目期数：各读音分支所列代表词至少出现一次的期次数（最多31）；同一期重复不加分。若各分支都无证据，此项均分。','- 常用程度：3＝日常／基础熟词锚点，2＝通用书面／正式词汇，1＝较专门锚点。本表是人工教学判断，未接入大型日语语料；不是JLPT官方等级或客观语频。','- 统计仅覆盖本册列出的代表词，词族扩展更丰富可能提高覆盖值；不是该字全部词的穷尽统计。精确字面匹配可能漏掉活用及异体表记。','- 多读词固執默认计入こしつ所在分支，合法读法こしゅう不重复计数。读音标准见学习册引用的辞典。','- **★为你刚答错的词：即使其读音分支权重低，也先修复，直至无选项提取正确。** 不将70%权重解释为另外30%可以不学。','','## 每个读音分支的权重','','| 字／组 | 读音或词内音形 | 代表词 | 主题次数 | 跨科目题数／期数 | 常用评分 | 组内权重 | 当前动作 |','|---|---|---|---:|---:|---:|---:|---|']
for f in output:
 for b in f['branches']:
  action='★先修复：'+'、'.join(b['recentWrongWords']) if b['recentWrongWords'] else '按权重复习；答对后降频'
  L.append(f"| {f['character']} | {b['reading']} | {'、'.join(b['words'])} | {b['targetQuestionCount']} | {b['crossSubjectQuestionCount']}／{b['crossSubjectPaperCount']} | {b['commonness']} | **{b['weightPercent']}%** | {action} |")
L+=['','## 实际怎么用','','同一汉字先选权重高的熟词当锚点，再背异读分支；例如興先固定興奮／復興／振興中的こう，再与興味きょうみ对照。每次仍需说出完整词，不只报单字读音。','', '本轮15个错词优先级高于此表：其中丘陵、兆し、猛烈、管轄等少例词没有完整多分支权重，仍须优先掌握。读音学会后，用不同题干及间隔复测验证，不能仅按频率删除低权重词。','']
(O/'kanji-reading-weights.md').write_text('\n'.join(L),encoding='utf-8')
book=O/'kanji-reading-word-families.md';t=book.read_text('utf-8');t=t.replace('## 使用方法','权重配套：[各读音的频率与复习权重](kanji-reading-weights.md)。\n\n## 使用方法',1);book.write_text(t,encoding='utf-8')
for f in output:
 if f['character'] in ['行','興','露','合','心','図']:print(f['character'],[(b['reading'],b['weightPercent'],b['targetQuestionCount'],b['crossSubjectPaperCount']) for b in f['branches']])
print('Verified families:',len(output),'branches:',sum(len(f['branches']) for f in output))
