#!/usr/bin/env python3
"""Build an evidence-labelled study index without changing the exam bundle."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / '考点分类索引'

# Semantic categories are separate from exam question types.
TAXONOMY = {
    'reading-sound': ('汉字与词汇', '汉字与读音对应'),
    'voicing': ('汉字与词汇', '清音与浊音辨析'),
    'long-vowel': ('汉字与词汇', '长音辨析'),
    'lexical-context': ('汉字与词汇', '语境中的词义与搭配'),
    'synonym': ('汉字与词汇', '近义改写与词义边界'),
    'usage': ('汉字与词汇', '词语适用对象与用法'),
    'concession': ('逻辑关系', '让步与逆接'),
    'condition': ('逻辑关系', '假定与条件'),
    'necessary': ('逻辑关系', '必要条件'),
    'counterfactual': ('逻辑关系', '反事实条件'),
    'cause': ('逻辑关系', '原因与理由'),
    'choice': ('逻辑关系', '比较与取舍'),
    'limit': ('逻辑关系', '限定与追加'),
    'degree': ('逻辑关系', '程度与否定呼应'),
    'honorific': ('主体与视角', '尊敬语与自谦语'),
    'benefactive': ('主体与视角', '授受视角'),
    'voice': ('主体与视角', '被动与使役方向'),
    'time': ('时间与说话人立场', '时间关系与先后'),
    'aspect': ('时间与说话人立场', '时制与持续状态'),
    'judgment': ('时间与说话人立场', '判断与评价'),
    'modality': ('时间与说话人立场', '可能性与情境制约'),
    'emotion': ('时间与说话人立场', '感叹、责备与反语'),
    'comparison': ('时间与说话人立场', '比况与特征描述'),
    'nominal': ('句子结构', '引用与名词化'),
    'modifier': ('句子结构', '修饰关系与中心词'),
    'fixed': ('句子结构', '固定句型连接'),
    'reference': ('篇章与阅读', '指代与回指'),
    'connection': ('篇章与阅读', '句间衔接与话语流程'),
    'explanation': ('篇章与阅读', '说明语气与文体'),
    'main-idea': ('篇章与阅读', '主旨与作者立场'),
    'reason-reading': ('篇章与阅读', '原因定位与推断'),
    'meaning-reading': ('篇章与阅读', '语句含义解释'),
    'compare-reading': ('篇章与阅读', '多方观点比较'),
    'information': ('篇章与阅读', '信息筛选与条件匹配'),
    'listening-action': ('听力能力', '行动与任务要求'),
    'listening-detail': ('听力能力', '关键信息提取'),
    'listening-main': ('听力能力', '主旨与说话人意图'),
    'listening-response': ('听力能力', '语用与即时应答'),
    'listening-integrated': ('听力能力', '综合信息与决策'),
}

# Pattern matches are candidates, never automatically promoted to reviewed tags.
PATTERNS = {
 'concession': 'とはいえ|ものを|ながらも|であれ|だろうと|であろうと|にしても|にせよ|といえども|にもかかわらず|たところで',
 'necessary': 'なくして|なしには|ないことには',
 'condition': 'とあれば|ならば|限り|にしては|としたら|とすれば',
 'cause': 'ばこそ|とあって|だけに|ゆえ|せい|おかげ|からこそ',
 'choice': 'くらいなら|ぐらいなら|よりも|にひきかえ',
 'limit': 'のみならず|に限らず|をも|はおろか|ばかりか|にすぎない|に過ぎない|ならでは|もさることながら',
 'degree': '極まり|限りだ|ほどのこと|てたまら|てならない',
 'honorific': 'おいで|お越し|伺|いらっしゃ|召し上が|ご覧|いたし|におかれまして',
 'benefactive': 'いただ|くださ|てもら|てくれ|てあげ',
 'time': 'とたん|や否や|が早いか|そばから|に先立|て以来|に際し|うえで',
 'judgment': 'に越したことはない|に違いない|に相違ない|とするには|までもない|べき',
 'modality': 'なくもない|かねない|かねる|ざるを得ない|わけにはいかない|てはいられない|てばかりもいられない|ほかない',
 'nominal': 'ということ|だってこと|のだと|とのこと',
 'comparison': 'みたい|かのよう|らしいところ',
 'connection': '^とはいえ$|^ただ$|^そこで$|^それでも$|^ちなみに$|^すなわち$|^つまり$|^ところが$',
 'reference': '^そうした|^そのような|^こうした',
}

# Read against full stems and choices, not copied from generic explanations.
REVIEWED_2025 = {
 1: (['reading-sound','voicing','long-vowel'], '頑丈→がんじょう；干扰项对比が／か与じょう／じょ。'),
 6: (['reading-sound','voicing'], '管轄→かんかつ；对比かつ／がつ，另有かい干扰。'),
 26: (['degree','modality'], 'とても与終わりそうにない呼应，强调一天内无法完成。'),
 27: (['necessary','counterfactual'], '協力なくしては実現しなかったであろう：无此合作便无法实现。'),
 28: (['choice','condition'], '乗るくらいなら…行くほうがいい：与其乘飞机，宁愿改用其他交通方式。'),
 29: (['judgment','condition'], '仮説を正しいとするには：认定假说正确所需的条件。'),
 30: (['voice','concession'], '選手がけがに悩まされる为受影响视角；ながらも连接克服困难的逆接。'),
 31: (['judgment'], '早く準備を始めるに越したことはない：早点准备最好。不能仅归为引用。'),
 32: (['counterfactual','aspect'], '渋滞していなければ…今頃…遊んでいたのに：与现状相反的持续状态设想。'),
 33: (['benefactive','emotion'], '余計なことをしてくれたものだ：くれる用于反语抱怨，ものだ表达感叹。'),
 34: (['comparison'], '仕事みたいなところがある：把谈话描述为工作的一种性质／侧面。'),
 35: (['modality'], '水不足を考えると喜んでばかりもいられない：情势不允许一直高兴。'),
 36: (['fixed','judgment'], '西山さんも西山さんなら課長も課長だ：NもNならNもNだ，对双方作负面评价。'),
 37: (['concession','nominal'], 'どんなに気をつけていても…起きてしまうのがトラブルだ：让步与の名词化。'),
 39: (['cause','time','nominal'], '入賞したことがよほどうれしかったのか、家に帰ってくるなり…：原因推测、名词化和立即发生。'),
 40: (['time','modifier','condition','reference'], 'よく考えたうえでの決断ならば…そうは思えない：先后、名词修饰、条件及回指。'),
 41: (['cause','explanation'], '全文说明猫靠气味确认对方；目がよくないからでもあります补充原因。'),
 42: (['explanation','aspect'], '前文叙述猫的一般习性；同じ反応を示すのです说明常态，不是过去回忆或样态推测。'),
 43: (['condition'], 'この習性を利用すれば、初対面のネコとも仲よくできます：利用习性为后项的条件。'),
 44: (['connection'], 'そこで承接猫不知道来者身份的问题，引出伸手指让猫闻的办法。'),
}

def cell(text):
    return re.sub(r'\s+', ' ', str(text)).replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;')

def main():
    raw = (ROOT / 'offline-exam-tool/data.js').read_text(encoding='utf-8')
    data = json.loads(raw.split('=', 1)[1].rstrip(';\n'))
    OUT.mkdir(parents=True, exist_ok=True)
    for sub in ('考点', '期次'):
        (OUT / sub).mkdir(exist_ok=True)
    rows, by_tag, terms = [], defaultdict(list), defaultdict(list)
    for year in data['years']:
        for category, questions in data['exams'][year].items():
            for q in questions:
                answer = q.get('rightAnswer')
                options = q.get('options', [])
                correct = options[answer-1] if isinstance(answer, int) and 1 <= answer <= len(options) else ''
                stem = q.get('question', '')
                group = int(q.get('groupNumber') or 0)
                tags = {}
                def add(tag, status, evidence):
                    tags[tag] = {'id': tag, 'status': status, 'evidence': evidence}
                target = ''
                marked = re.findall(r'⟦u⟧(.*?)⟦/u⟧|【([^】]+)】', stem)
                if category in ('文字','词汇'):
                    if category == '文字' or group == 3:
                        target = ' / '.join(a or b for a,b in marked)
                    elif group == 2:
                        target = correct
                    elif group == 4:
                        # Do not treat a full instruction or sentence as a target word.
                        target = stem.strip() if len(stem.strip()) <= 30 and '\n' not in stem.strip() else ''
                    tag = 'reading-sound' if category == '文字' else {2:'lexical-context',3:'synonym',4:'usage'}.get(group)
                    if tag:
                        add(tag, '题型映射', '由原科目与大题编号确定能力方向，尚未逐题核对细分语义。')
                elif category == '语法':
                    # A star-position answer is only a fragment, not the tested construction.
                    if group != 6:
                        target = correct
                        for tag, pattern in PATTERNS.items():
                            match = re.search(pattern, correct)
                            if match:
                                add(tag, '候选', f'正确选项命中「{match.group()}」；须结合题干复核。')
                elif category == '阅读':
                    # Last question sentence only; avoid matching words inside the passage.
                    prompt = stem.strip().split('\n')[-1]
                    for tag, pattern in {
                        'main-idea':'最も言いたい|最も伝えたい|筆者の考え|筆者は.*考えて',
                        'reason-reading':'なぜ|理由',
                        'meaning-reading':'どういうこと|どのようなこと|どういう意味',
                        'compare-reading':'AとB|ＡとＢ|共通',
                        'information':'応募できる|条件を満た|申し込|申込',
                    }.items():
                        if re.search(pattern, prompt):
                            add(tag, '候选', '问句线索：'+prompt[:180])
                elif category == '听力':
                    listening_group = group-50 if 51 <= group <= 55 else group
                    tag = {1:'listening-action',2:'listening-detail',3:'listening-main',4:'listening-response',5:'listening-integrated'}.get(listening_group)
                    if tag:
                        add(tag, '题型映射', '仅按听力大题映射训练能力；未听音频，未判定具体语言考点。')
                if year == '2025.12' and category in ('文字','语法') and q['number'] in REVIEWED_2025:
                    tag_ids, evidence = REVIEWED_2025[q['number']]
                    tags = {}
                    for tag in tag_ids:
                        add(tag, '已核对', evidence)
                issues = []
                if q['id'] == 'markdown-2025.12-language-38':
                    issues.append('现有解析排序2→3→1→4无法与题干连成通顺句；考点暂不定案，原题及答案均未修改。')
                row = {'id':q['id'],'year':year,'category':category,'number':q['number'],
                       'groupNumber':group,'target':target,'tags':list(tags.values()),
                       'status':'已核对' if any(t['status']=='已核对' for t in tags.values()) else '待核对',
                       'issues':issues,'question':q}
                rows.append(row)
                for tag in tags:
                    by_tag[tag].append(row)
                if target:
                    terms[target].append(row)
    ids = [r['id'] for r in rows]
    assert len(ids) == len(set(ids)), 'Duplicate question IDs'
    assert all(t['id'] in TAXONOMY for r in rows for t in r['tags'])
    anchors = {r['id']: 'q-'+hashlib.sha256(r['id'].encode()).hexdigest()[:16] for r in rows}
    def link(r, prefix=''):
        return f"[{r['year']} {r['category']} Q{r['number']}]({prefix}期次/{r['year']}.md#{anchors[r['id']]})"
    for year in data['years']:
        lines = [f'# {year} 题目索引', '', '[返回目录](../README.md)', '', '原题按原样保留。共享文章可能存于本组首题；请一并参看相邻题，图片与音频链接指向项目原资源。', '']
        for r in (r for r in rows if r['year']==year):
            q = r['question']
            lines += [f'<a id="{anchors[r["id"]]}"></a>', f'## {r["category"]} Q{r["number"]}', '', f'题目 ID：`{r["id"]}`', '', '分类：'+('；'.join(f'[{TAXONOMY[t["id"]][1]}](../考点/{t["id"]}.md)（{t["status"]}）' for t in r['tags']) or '待分类'), '']
            if r['target']:
                lines += ['检索词条／正确选项：'+r['target'], '']
            for t in r['tags']:
                lines += [f'- {TAXONOMY[t["id"]][1]}：{t["evidence"]}']
            lines += ['', *['待核查：'+x for x in r['issues']], '']
            for field in ('passage','question','subQuestion'):
                if q.get(field): lines += [str(q[field]), '']
            lines += [f'{i}. {x}' for i,x in enumerate(q.get('options',[]),1)]
            lines += ['', f'原题库答案：{q.get("rightAnswer")}', '']
            for media in [*q.get('images',[]), q.get('audio')]:
                if isinstance(media,str) and media:
                    url = media if media.startswith(('http://','https://')) else '../../../'+quote(media)
                    lines += [f'[原题媒体]({url})', '']
        (OUT/'期次'/f'{year}.md').write_text('\n'.join(lines),encoding='utf-8')
    for tag,(parent,name) in TAXONOMY.items():
        lines = [f'# {parent} · {name}', '', '[返回目录](../README.md)', '', '“已核对”仅指本次核对了分类；不代表已重新校勘原始真题或答案。“候选”和“题型映射”仍需逐题复核。', '', '| 题目 | 词条／正确选项 | 状态 | 归类依据 |', '|---|---|---|---|']
        for r in by_tag[tag]:
            t = next(t for t in r['tags'] if t['id']==tag)
            lines.append(f'| {link(r,"../")} | {cell(r["target"])} | {t["status"]} | {cell(t["evidence"])} |')
        (OUT/'考点'/f'{tag}.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    lines = ['# 词条与正确选项索引', '', '[返回目录](README.md)', '', '文字题取强调词；语境选词取正确选项；近义题取强调词；用法题取短词条。语法非排序题暂以正确选项作检索键，不等同于标准句型名。排序题不把星号片段当完整考点。未提取到词条的题仍保留在全量索引中。', '', '| 检索键 | 关联题目 |', '|---|---|']
    lines += [f'| {cell(term)} | '+ '；'.join(link(r) for r in rs)+' |' for term,rs in sorted(terms.items())]
    (OUT/'词条索引.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    stats = {'sourceSha256':hashlib.sha256(raw.encode()).hexdigest(),'periods':len(data['years']),
             'questions':len(rows),'reviewed':sum(r['status']=='已核对' for r in rows),
             'withTags':sum(bool(r['tags']) for r in rows),'withoutTags':sum(not r['tags'] for r in rows),
             'withTarget':sum(bool(r['target']) for r in rows),'tagAssignments':dict(Counter(t['status'] for r in rows for t in r['tags'])),
             'categories':dict(Counter(r['category'] for r in rows))}
    (OUT/'题目索引.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    (OUT/'分类目录.json').write_text(json.dumps([{'id':k,'parent':v[0],'name':v[1]} for k,v in TAXONOMY.items()],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'统计.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines = ['# N1 考点分类目录与题目索引', '', f'覆盖 {stats["periods"]} 个期次、{len(rows)} 道题；保留原题 ID、题干、选项、答案与媒体定位。', '',
      '## 使用入口', '', '- [按词条与正确选项查题](词条索引.md)', '- [全量机器可读题目索引](题目索引.jsonl)', '- [分类目录数据](分类目录.json)', '- [覆盖统计](统计.json)', '- [待分类与待核查](待分类.md)', '',
      '## 分类状态', '', f'- 已逐题核对分类：{stats["reviewed"]} 道（2025.12 首批）。', f'- 有分类标签：{stats["withTags"]} 道；尚无标签：{stats["withoutTags"]} 道。', f'- 有词条或正确选项检索键：{stats["withTarget"]} 道。',
      '- 已核对：本次依据题干、选项及必要的共享文章判断考点。', '- 候选：根据正确选项的特定表达或阅读问句提出，未人工逐题确认。', '- 题型映射：只有宽泛训练能力，不代表已完成具体考点标注。',
      '- 一题可关联多个考点，分类计数不能相加当作题目总数。年份与题型仅作为筛选维度。',
      '- 原解析含自动生成模板，不用通用解析全文做关键词分类。听力未逐题听音，不从空题干或通用解析推断细分考点。', '', '## 考点目录', '', '| 大类 | 考点 | 题数 | 已核对 |', '|---|---|---:|---:|']
    for tag,(parent,name) in TAXONOMY.items():
        reviewed = sum(any(t['id']==tag and t['status']=='已核对' for t in r['tags']) for r in by_tag[tag])
        lines.append(f'| {parent} | [{name}](考点/{tag}.md) | {len(by_tag[tag])} | {reviewed} |')
    lines += ['', '## 按期次回查', '', *[f'- [{year}](期次/{year}.md)' for year in data['years']], '', '## 维护', '',
      '运行 `python3 tools/build_knowledge_point_index.py` 从当前离线题库重建。生成目录可覆盖；分类规则和本次核对依据维护在该脚本中。',
      '此索引不修改网页、答案或答题历史。语法教材定位可参照项目已有的《新完全マスター》映射文件；本版不自动填充未经核对的章节或页码。', '']
    lines[2:2] = ['> 本目录为早期跨科目分类草稿。文字・词汇（問題1—4）的正式分类及全量标签请使用[文字・词汇分类知识库](../N1考试知识库/文字词汇分类/README.md)，语法（問題5—7）最近10期的正式分类及标签请使用[语法分类知识库](../N1考试知识库/语法分类/README.md)。这些范围不再以本草稿标签作为分类依据。', '']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    pending = ['# 待分类与待核查', '', '[返回目录](README.md)', '', '下列为没有任何考点标签的题。已有“候选／题型映射”但尚未核对的题见各考点页。', '']
    pending += [f'- {link(r)}：`{r["id"]}`'+('；'+'；'.join(r['issues']) if r['issues'] else '') for r in rows if not r['tags']]
    (OUT/'待分类.md').write_text('\n'.join(pending)+'\n',encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
