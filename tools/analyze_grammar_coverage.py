"""Point/type/frequency coverage index; not a calibrated probability.

Default: leave one complete exam out and use every other exam as evidence.
"""
from pathlib import Path
from collections import Counter
from math import exp
import json,hashlib,argparse
from grammar_coverage_features import features,normalized

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--mode',choices=['leave-one-exam-out','chronological'],default='leave-one-exam-out')
MODE=parser.parse_args().mode
OUT=ROOT/'11 Learning Analytics/grammar-coverage'
if MODE=='leave-one-exam-out':OUT=OUT/'leave-one-exam-out'
OUT.mkdir(exist_ok=True,parents=True)
SOURCE=ROOT/'offline-exam-tool/data.js'
data=json.loads(SOURCE.read_text(encoding='utf-8-sig').split('=',1)[1].rstrip(';\n '))
annotations=[json.loads(x) for x in (ROOT/'output/N1考试知识库/语法分类/题目标签.jsonl').read_text(encoding='utf8').splitlines()]
source_rows={q['id']:q for e in data['exams'].values() for q in e['语法']}
assert len(source_rows)==len(annotations)==609
for r in annotations:
    for field in ('question','options','rightAnswer','groupNumber','passage','subQuestion'):
        assert r['sourceQuestion'][field]==source_rows[r['id']][field],(r['id'],field)
    r['features']=features(r)
annotations.sort(key=lambda r:(r['year'],int(r['questionNumber'])))
PROFILES={
    'strict':{'related':.5,'superfamily':.25,'cross56':.65,'cross57':.4,'cross67':.4,'base':.5,'tau':5,'combination':.35,'broad':.1},
    'central':{'related':.65,'superfamily':.4,'cross56':.8,'cross57':.6,'cross67':.55,'base':.6,'tau':3,'combination':.25,'broad':.15},
    'generous':{'related':.8,'superfamily':.55,'cross56':.9,'cross57':.75,'cross67':.7,'base':.7,'tau':2,'combination':.15,'broad':.2},
}
SUPERFAMILIES=[
    set('negative_emphasis limitation partial_negation qualified_affirmation negative_possibility non_absolute'.split()),
    set('occasion_start sequence_start end_boundary before_action immediate_sequence temporal_boundary temporal_reference sequence'.split()),
    set('during_change persistent_change ongoing_change ongoing_state left_state unchanged_state direction_toward_now direction_future imminent_completion'.split()),
    set('necessary_basis continuing_condition sufficient_condition commitment_condition situational_condition hypothetical_condition difficult_hypothesis purpose_condition counterfactual'.split()),
    set('concession concession_connector unconditional_concession contrast contrary_expectation contrast_connector contrary_connector contrast_discourse'.split()),
    set('background_cause evidential_cause additional_cause special_cause formal_cause expected_cause adverse_cause excess_cause explanatory_cause contribution_cause joint_cause causal_discourse cause_connector'.split()),
    set('evidential_inference forecast possibility adverse_possibility strong_inference expectation hypothetical_possibility'.split()),
    set('honorific_sonkei honorific_humble honorific_request benefactive_receive benefactive_give benefactive_give_out subject_viewpoint'.split()),
    set('situational_inability no_means psychological_difficulty polite_inability completion_ability social_constraint'.split()),
    set('explanatory_definition explanatory_modality reformulation reformulation_connector summary'.split()),
    set('anaphora_specific anaphora_class deixis_current deictic_method reference subject_reference subject_ellipsis'.split()),
    set('illustration extreme_example case_emphasis degree_emphasis extreme_degree'.split()),
    set('nominal_modifier relative_clause quote_noun multiple_modifiers'.split()),
    set('intention attempt_intention volitional_quote demonstration_intention decision'.split()),
    set('temporal_generic general_rule general_explanation ongoing_generic'.split()),
    set('extreme_evaluation excess_evaluation evaluation_conclusion author_evaluation positive_evaluation'.split()),
]

def type_weight(a,b,p):
    if a==b:return 1.
    return p['cross'+''.join(map(str,sorted((a,b))))]

def point_match(k,f,h,p):
    if k in h['features'] and f['family']==h['features'][k]['family']:return 1.
    if f['family'] and any(v['family']==f['family'] for v in h['features'].values()):return p['related']
    if f['family'] and any(f['family'] in group and any(v['family'] in group for v in h['features'].values()) for group in SUPERFAMILIES):return p['superfamily']
    return 0.

def support_score(sims,p):
    """Maximum over evidence-strength tiers ensures monotonicity.

    Adding examples or increasing any similarity never lowers the result.
    More weak examples cannot exceed their similarity ceiling.
    """
    positive=[s for s in sims if s>0]
    best={'score':0.,'strength':0.,'count':0}
    for threshold in sorted(set(positive)):
        count=sum(s+1e-12>=threshold for s in positive)
        score=threshold*(p['base']+(1-p['base'])*(1-exp(-count/p['tau'])))
        if score>best['score']:best={'score':score,'strength':threshold,'count':count}
    return best

def evaluate(q,history,p,detail=False):
    atoms=[];pair_sims=[];near=[]
    for k,f in q['features'].items():
        ss=[];exact=[]
        for h in history:
            content=point_match(k,f,h,p)
            if not content and set(q['tags']).intersection(h['tags']):content=p['broad']
            ss.append(content*type_weight(q['problemNumber'],h['problemNumber'],p))
            if point_match(k,f,h,p)==1:exact.append(h)
        support=support_score(ss,p)
        atoms.append({'point':k,'family':f['family'],'weight':f['weight'],**support,
                      'exact_history_count':len(exact),'exact_same_type_count':sum(h['problemNumber']==q['problemNumber'] for h in exact)})
    total_weight=sum(f['weight'] for f in q['features'].values())
    for h in history:
        content=sum(f['weight']*point_match(k,f,h,p) for k,f in q['features'].items())/total_weight
        if not content and set(q['tags']).intersection(h['tags']):content=p['broad']
        similarity=content*type_weight(q['problemNumber'],h['problemNumber'],p)
        pair_sims.append(similarity)
        if detail:near.append({'id':h['id'],'year':h['year'],'number':h['questionNumber'],'group':h['problemNumber'],
                               'construction':h['construction'],'similarity':similarity,'point_similarity':content,
                               'type_similarity':type_weight(q['problemNumber'],h['problemNumber'],p)})
    point_score=sum(a['weight']*a['score'] for a in atoms)/total_weight
    combination=support_score(pair_sims,p)
    score=(1-p['combination'])*point_score+p['combination']*combination['score']
    result={'score':score,'point_score':point_score,'combination':combination,
            'all_points_seen':all(a['exact_history_count']>0 for a in atoms),
            'all_points_seen_same_type':all(a['exact_same_type_count']>0 for a in atoms),
            'max_pair_similarity':max(pair_sims,default=0)}
    if detail:result.update(atoms=atoms,nearest=sorted(near,key=lambda x:x['similarity'],reverse=True)[:5])
    return result

history=[];results=[]
for year in sorted(data['exams']):
    qs=[r for r in annotations if r['year']==year]
    if MODE=='leave-one-exam-out':
        history=[r for r in annotations if r['year']!=year]
        assert len({h['year'] for h in history})==30
        assert not {q['id'] for q in qs}.intersection(h['id'] for h in history)
        assert len(history)+len(qs)==609
    for q in qs:
        assert all(h['year']!=year if MODE=='leave-one-exam-out' else h['year']<year for h in history)
        entry={'year':year,'id':q['id'],'number':q['questionNumber'],'group':q['problemNumber'],
               'construction':q['construction'],'evidence':q['evidence'],'tags':q['tags'],'notes':q['notes'],'features':q['features'],
               'history_questions':len(history),'history_papers':len(set(h['year'] for h in history))}
        for name,p in PROFILES.items():entry[name]=evaluate(q,history,p,detail=name=='central')
        entry['broad_primary_tag_seen']=any(q['primaryTag'] in h['tags'] for h in history)
        entry['literal_construction_seen']=any(normalized(q['construction'])==normalized(h['construction']) for h in history)
        results.append(entry)
    if MODE=='chronological':history.extend(qs)

def aggregate(rs):
    return {'questions':len(rs),**{name:sum(r[name]['score'] for r in rs)/len(rs) for name in PROFILES},
            'all_points_seen':sum(r['central']['all_points_seen'] for r in rs)/len(rs),
            'all_points_seen_same_type':sum(r['central']['all_points_seen_same_type'] for r in rs)/len(rs),
            'broad_primary_tag_seen':sum(r['broad_primary_tag_seen'] for r in rs)/len(rs),
            'literal_construction_seen':sum(r['literal_construction_seen'] for r in rs)/len(rs),
            'central_ge_80':sum(r['central']['score']>=.8 for r in rs),
            'central_lt_50':sum(r['central']['score']<.5 for r in rs)}

summary={}
for n in (31,10,6,4):
    years=sorted(data['exams'])[-n:];rs=[r for r in results if r['year'] in years]
    summary[str(n)]={str(g):aggregate([r for r in rs if r['group']==g]) for g in (5,6,7)}
    summary[str(n)]['total']=aggregate(rs)
    summary[str(n)]['exclude_flagged_queries']=aggregate([r for r in rs if not r['notes']])
per_year={y:{str(g):aggregate([r for r in results if r['year']==y and r['group']==g]) for g in (5,6,7)} for y in sorted(data['exams'])}
per_tag={}
for tag in sorted({t for r in results for t in r['tags']}):
    rs=[r for r in results if r['year']>='2021.07' and tag in r['tags']]
    if rs:per_tag[tag]=aggregate(rs)

payload={'model':'Uncalibrated monotone historical-point coverage index; not exam accuracy or fitted probability.',
         'evaluation_mode':MODE,
         'data_source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'papers':31,'questions':609,
         'profiles':PROFILES,'summary':summary,'per_year':per_year,'last10_per_tag':per_tag,'rows':results}
(OUT/'results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
print('LOWEST RECENT')
for r in sorted([r for r in results if r['year']>='2021.07'],key=lambda r:r['central']['score'])[:12]:
    print(r['year'],r['number'],r['construction'],round(r['central']['score'],3),r['central']['nearest'][:2])
