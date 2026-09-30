"""Conditional guessing model, not an observed learner accuracy estimate."""
from pathlib import Path
import json

out = Path(__file__).resolve().parents[1] / '11 Learning Analytics' / 'vocabulary-coverage'
rows = json.loads((out/'question-audit.json').read_text(encoding='utf-8'))

def expectation(row, eliminate):
    h=row['all_options']
    if row['group']==4:
        return 1.0 if h['target'] else .25
    # Familiar answer options do not identify an unknown synonym target.
    if row['group']==3 and not h['target']:
        return .25
    if h['answer']:
        return 1.0
    k=sum(h['option_hits']) if eliminate else 0
    return 1/(4-k)

results={}
for n in (10,6,4):
    years=sorted({r['year'] for r in rows})[-n:]
    subset=[r for r in rows if r['year'] in years]
    results[str(n)]={
        'questions':len(subset),
        'known_answer_else_random':sum(expectation(r,False) for r in subset)/len(subset),
        'with_perfect_valid_elimination':sum(expectation(r,True) for r in subset)/len(subset),
        'questions_helped_by_elimination':sum(expectation(r,True)>expectation(r,False) for r in subset),
    }
payload={
    'assumptions':[
        'Historical option lexicon and chronological matching inherited from question-audit.json.',
        'Group 2: a familiar correct answer is recognized with certainty; familiar distractors are ruled out correctly.',
        'Group 3: the target must be familiar before either recognition or elimination is allowed.',
        'Group 4: familiar target means perfect usage mastery; unfamiliar target means random guessing.',
        'Choose uniformly among remaining candidates, no mistakes in elimination.',
        'Unfamiliar words yield no contextual or character-based inferences; no vocabulary learned outside historical options.',
        'These assumptions are unvalidated learner-behavior scenarios, not measured accuracy or an absolute upper bound.'
    ],
    'results':results
}
(out/'elimination-model.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
