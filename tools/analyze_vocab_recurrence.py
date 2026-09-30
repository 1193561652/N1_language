"""Chronological vocabulary backtest; never learn from the held-out paper."""
from pathlib import Path
from functools import lru_cache
import json, re, unicodedata, hashlib
from collections import Counter
from janome.tokenizer import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '11 Learning Analytics' / 'vocabulary-coverage'
OUT.mkdir(exist_ok=True)
source = ROOT / 'offline-exam-tool/data.js'
data = json.loads(source.read_text(encoding='utf-8-sig').split('=',1)[1].rstrip(';\n '))
tokenizer = Tokenizer()

def clean(s):
    return unicodedata.normalize('NFKC', re.sub(r'⟦/?u⟧|【|】|</?u>', '', s))

@lru_cache(None)
def key(s):
    if clean(s).strip() in ('かたくな','かたくなに','かたくなな'): return ('かたくな',)
    result = []
    for t in tokenizer.tokenize(clean(s)):
        pos = t.part_of_speech.split(',')
        if pos[0] in ('名詞','動詞','形容詞','副詞','連体詞','接頭詞'):
            if pos[0]=='名詞' and pos[1] in ('数',): continue
            if t.base_form in ('する','いる','ある','なる','できる'): continue
            result.append(t.base_form if t.base_form != '*' else t.surface)
    return tuple(result) or (clean(s).strip(),)

def target(q):
    if q['groupNumber']==2: return q['options'][q['rightAnswer']-1]
    if q['groupNumber']==4: return clean(q['question']).strip()
    m = re.search(r'【(.*?)】|⟦u⟧(.*?)⟦/u⟧|<u>(.*?)</u>',q['question'])
    assert m, q['id']
    return next(x for x in m.groups() if x is not None)

def add(index, text, witness):
    k=key(text)
    for n in range(1,min(10,len(k))+1):
        for i in range(len(k)-n+1): index.setdefault(k[i:i+n],witness | {'text':text})

indexes = {'all_options':{}, 'core_options':{}, 'core_plus_stems':{}, 'all_options_plus_synonym_targets':{}, 'all_options_plus_all_stems':{}, 'all_groups1to4_full_text':{}}
rows=[]; periods=[]; inventory=set()
for year in sorted(data['exams']):
    qs=data['exams'][year]['词汇']
    assert len(qs)==19 and Counter(q['groupNumber'] for q in qs)=={2:7,3:6,4:6}
    for q in qs:
        assert len(q['options'])==4 and 1<=q['rightAnswer']<=4
        t=target(q); tk=key(t); answer=q['options'][q['rightAnswer']-1]
        assert tk, (year,q['number'],t)
        r={'year':year,'id':q['id'],'number':q['number'],'group':q['groupNumber'],'target':t,'key':tk,'answer':answer}
        for name,idx in indexes.items():
            hit=idx.get(tk)
            r[name]={'target':bool(hit),'witness':hit}
            if q['groupNumber'] in (2,3):
                hits=[bool(key(o)) and key(o) in idx for o in q['options']]
                r[name].update(option_hits=hits,answer=hits[q['rightAnswer']-1],both=bool(hit) and hits[q['rightAnswer']-1],all4=all(hits))
        tokens=[t for o in q['options'] for t in key(o)]
        r['option_lexical_tokens']=len(tokens)
        r['known_option_lexical_tokens']=sum((t,) in indexes['all_options'] for t in tokens)
        rows.append(r)
    periods.append({'year':year,'historical_option_lemmas':len(inventory)})
    # Only now add this paper, after every held-out question has been assessed.
    for q in qs:
        w={'year':year,'number':q['number']}
        for i,o in enumerate(q['options']):
            add(indexes['all_options'],o,w|{'option':i+1})
            for name in ('all_options_plus_synonym_targets','all_options_plus_all_stems','all_groups1to4_full_text'):
                add(indexes[name],o,w|{'option':i+1})
            inventory.update(key(o))
            if q['groupNumber'] in (2,3):
                for name in ('core_options','core_plus_stems'): add(indexes[name],o,w|{'option':i+1})
        if q['groupNumber']==4:
            for name in ('core_options','core_plus_stems'):add(indexes[name],target(q),w|{'field':'target'})
        if q['groupNumber']==3:add(indexes['core_plus_stems'],target(q),w|{'field':'target'})
        add(indexes['all_options_plus_all_stems'],q['question'],w|{'field':'question'})
        if q['groupNumber'] in (3,4):
            add(indexes['all_options_plus_all_stems'],target(q),w|{'field':'target'})
        if q['groupNumber']==3:
            add(indexes['all_options_plus_synonym_targets'],target(q),w|{'field':'target'})
        add(indexes['all_groups1to4_full_text'],q['question'],w|{'field':'question'})
        if q['groupNumber'] in (3,4):
            add(indexes['all_groups1to4_full_text'],target(q),w|{'field':'target'})
    for q in data['exams'][year]['文字']:
        w={'year':year,'number':q['number']}
        add(indexes['all_groups1to4_full_text'],q['question'],w|{'field':'question'})
        add(indexes['all_groups1to4_full_text'],target(q),w|{'field':'target'})

def summarize(rs,name):
    counts={'questions':len(rs),'target':sum(r[name]['target'] for r in rs)}
    counts['option_lexical_tokens']=sum(r['option_lexical_tokens'] for r in rs)
    counts['known_option_lexical_tokens']=sum(r['known_option_lexical_tokens'] for r in rs)
    for g in (2,3,4):
        gs=[r for r in rs if r['group']==g]
        counts['group'+str(g)]={'n':len(gs),'target':sum(r[name]['target'] for r in gs)}
        if g in (2,3):
            for field in ('answer','both','all4'):counts['group'+str(g)][field]=sum(r[name][field] for r in gs)
            counts['group'+str(g)]['option_hits']=sum(sum(r[name]['option_hits']) for r in gs)
    counts['target_and_synonym_answer']=sum(r[name]['both'] if r['group']==3 else r[name]['target'] for r in rs)
    return counts

summary={'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'papers':len(periods),'questions':len(rows),'option_lemma_types':len(inventory),'periods':{}}
for year in sorted(data['exams']):summary['periods'][year]={name:summarize([r for r in rows if r['year']==year],name) for name in indexes}
for n in (4,6,10):
    ys=sorted(data['exams'])[-n:]
    summary['last'+str(n)]={name:summarize([r for r in rows if r['year'] in ys],name) for name in indexes}
(OUT/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'question-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='periods'},ensure_ascii=False,indent=2))
print('LAST TEN PERIODS')
for y in sorted(data['exams'])[-10:]:print(y,json.dumps(summary['periods'][y]['all_options'],ensure_ascii=False))
