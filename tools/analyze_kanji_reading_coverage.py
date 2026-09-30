"""Backtest written target-word coverage, conditional on mastering readings."""
import contextlib
import io
import json
with contextlib.redirect_stdout(io.StringIO()):
    import analyze_vocab_recurrence as v

indexes={'past_reading_targets':{},'past_vocabulary_full_text':{},'past_groups1to4_full_text':{}}
rows=[]
for year in sorted(v.data['exams']):
    exam=v.data['exams'][year]
    assert len(exam['文字'])==6
    for q in exam['文字']:
        t=v.target(q)
        assert v.key(t)
        rows.append({'year':year,'number':q['number'],'target':t,'correct_reading':q['options'][q['rightAnswer']-1],
                     'matches':{name:index.get(v.key(t)) for name,index in indexes.items()}})
    for q in exam['词汇']:
        w={'year':year,'number':q['number']}
        for name in ('past_vocabulary_full_text','past_groups1to4_full_text'):
            v.add(indexes[name],q['question'],w|{'field':'question'})
            if q['groupNumber'] in (3,4):v.add(indexes[name],v.target(q),w|{'field':'target'})
            for i,o in enumerate(q['options']):v.add(indexes[name],o,w|{'option':i+1})
    for q in exam['文字']:
        w={'year':year,'number':q['number']}
        v.add(indexes['past_reading_targets'],v.target(q),w|{'field':'target'})
        v.add(indexes['past_groups1to4_full_text'],q['question'],w|{'field':'question'})
        v.add(indexes['past_groups1to4_full_text'],v.target(q),w|{'field':'target'})

result={'scope':'31 papers 2010.07-2025.12; 186 reading questions. Excludes unverified mappings from wrong kana reading options to independent lexemes.',
        'interpretation':'Written-word recurrence; mastery of the correct contextual reading is assumed, not verified by recurrence. No character-level inference or distractor elimination modeled.',
        'windows':{}}
for n in (10,6,4):
    years=sorted(v.data['exams'])[-n:];rs=[r for r in rows if r['year'] in years]
    result['windows'][str(n)]={name:{'hits':sum(bool(r['matches'][name]) for r in rs),'total':len(rs),
        'coverage':sum(bool(r['matches'][name]) for r in rs)/len(rs),
        'perfect_reading_else_random':.25+.75*sum(bool(r['matches'][name]) for r in rs)/len(rs)} for name in indexes}
result['latest']=[r for r in rows if r['year']=='2025.12']
(v.OUT/'reading-coverage-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
(v.OUT/'reading-question-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
