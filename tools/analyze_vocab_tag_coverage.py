"""Join reviewed problem-scoped tags to chronological coverage evidence."""
from pathlib import Path
import json

root=Path(__file__).resolve().parents[1]
out=root/'11 Learning Analytics/vocabulary-coverage'
taxonomy=root/'output/N1考试知识库/文字词汇分类'
data=json.loads((root/'offline-exam-tool/data.js').read_text(encoding='utf-8-sig').split('=',1)[1].rstrip(';\n '))
annotations=[json.loads(s) for s in (taxonomy/'题目标签.jsonl').read_text(encoding='utf8').splitlines()]
vocab={r['id']:r for r in json.loads((out/'question-audit.json').read_text(encoding='utf8'))}
reading={(r['year'],r['number']):r for r in json.loads((out/'reading-question-audit.json').read_text(encoding='utf8'))}
questions={q['id']:q for e in data['exams'].values() for cat in ('文字','词汇') for q in e[cat]}
for a in annotations:
    for field in ('question','options','rightAnswer','groupNumber'):
        assert a['sourceQuestion'][field]==questions[a['id']][field],(a['id'],field)

groups={
    '动词读音':{'language.q1.verb'},
    '汉字读音（名词与汉字熟语）':{'language.q1.noun'},
    'い形容词读音':{'language.q1.adjective.i'},
    'しい形容词（問題2—3）':{'language.q2.adjective.shii','language.q3.adjective.shii'},
    'らか/やか形容词读音':{'language.q1.adjective.raka','language.q1.adjective.yaka'},
    '片假名（問題2—3）':{'language.q2.katakana','language.q3.katakana'},
}
rows=[]
for a in annotations:
    names=[name for name,tags in groups.items() if tags.intersection(a['tags'])]
    if not names:continue
    match=reading[a['year'],a['questionNumber']]['matches']['past_groups1to4_full_text'] if a['problemNumber']==1 else vocab[a['id']]['all_groups1to4_full_text']['witness']
    rows.append({'year':a['year'],'number':a['questionNumber'],'id':a['id'],'lemma':a['lemma'],'categories':names,'covered':bool(match),'witness':match})
summary={}
for name in groups:
    summary[name]={}
    for n in (31,10,6,4):
        years=sorted(data['exams'])[-n:]
        rs=[r for r in rows if name in r['categories'] and r['year'] in years]
        hits=sum(r['covered'] for r in rs)
        summary[name][str(n)]={'hits':hits,'total':len(rs),'coverage':hits/len(rs) if rs else None}
result={'scope':'Existing taxonomy: reading categories in group 1; shii and katakana tags in groups 2-3. All prior groups 1-4 written vocabulary used for matching. Wrong kana distractors not mapped to independent lexical items.','validation':'All 775 source questions match taxonomy snapshots for question/options/answer/group.','summary':summary,'rows':rows}
(out/'tag-coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
for r in rows:
    if any(x in r['categories'] for x in ['い形容词读音','らか/やか形容词读音','しい形容词（問題2—3）']):print(r)
