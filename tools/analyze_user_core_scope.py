"""User scope: Q1/Q3 targets+options, Q2/Q4 options only. No other stems.

Lexical normalization is separate from the hypothetical error-free elimination
model. Kana homophones cannot establish reliable elimination on their own.
"""
from pathlib import Path
from functools import lru_cache
from collections import Counter
import argparse,json,re,unicodedata,hashlib
from janome.tokenizer import Tokenizer

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--mode',choices=('leave-one-exam-out','chronological'),default='leave-one-exam-out')
MODE=parser.parse_args().mode
OUT=ROOT/'11 Learning Analytics/vocabulary-coverage/user-core-scope'
if MODE=='leave-one-exam-out':OUT=OUT/MODE
OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'offline-exam-tool/data.js'
data=json.loads(source.read_text(encoding='utf-8-sig').split('=',1)[1].rstrip(';\n '))
T=Tokenizer()
def clean(s):return unicodedata.normalize('NFKC',re.sub(r'⟦/?u⟧|【|】|</?u>','',s))
@lru_cache(None)
def key(s):
    if clean(s).strip() in ('かたくな','かたくなに','かたくなな'):return ('かたくな',)
    result=[]
    for t in T.tokenize(clean(s)):
        pos=t.part_of_speech.split(',')
        if pos[0] not in ('名詞','動詞','形容詞','副詞','連体詞','接頭詞'):continue
        if pos[0]=='名詞' and pos[1]=='数':continue
        if t.base_form in ('する','いる','ある','なる','できる'):continue
        result.append(t.base_form if t.base_form!='*' else t.surface)
    return tuple(result) or (clean(s).strip(),)
def target(q):
    if q['groupNumber']==2:return q['options'][q['rightAnswer']-1]
    if q['groupNumber']==4:return clean(q['question']).strip()
    m=re.search(r'【(.*?)】|⟦u⟧(.*?)⟦/u⟧|<u>(.*?)</u>',q['question'])
    assert m,q['id']
    return next(x for x in m.groups() if x is not None)

mapping={}
for line in (ROOT/'tools/reading_option_lexemes.tsv').read_text(encoding='utf8').splitlines():
    if not line or line.startswith('#'):continue
    kana,forms=line.split()
    if kana in mapping:assert mapping[kana]==forms.split('|'),kana
    mapping[kana]=forms.split('|')

def forms(q,i,homophones):
    if i==q['rightAnswer']-1:return [target(q)]
    candidates=mapping.get(q['options'][i],[])
    # Restrictive sensitivity: do not choose a kanji spelling for a multivalent
    # kana option. The broader scenario assumes study of listed common senses.
    return candidates if homophones or len(candidates)==1 else []

def run(homophones):
    idx={};rows=[];unmapped=Counter()
    def add(text,w):
        k=key(text)
        for n in range(1,min(10,len(k))+1):
            for i in range(len(k)-n+1):idx.setdefault(k[i:i+n],w|{'text':text})
    def known(text):return idx.get(key(text))
    def learn(year):
        qs=data['exams'][year]['文字']+data['exams'][year]['词汇']
        for q in qs:
            g=q['groupNumber'];w={'year':year,'number':q['number'],'group':g}
            if g in (1,3):add(target(q),w|{'field':'marked_target'})
            for i,o in enumerate(q['options']):
                if g==1:
                    fs=forms(q,i,homophones)
                    if not fs:continue
                    for f in fs:add(f,w|{'option':i+1,'kana':o,'normalization':'common lexical spelling; multiple spellings are a sensitivity assumption'})
                    add(o,w|{'option':i+1,'normalization':'confirmed real-word kana'})
                else:add(o,w|{'option':i+1})
    for exam in data['exams'].values():
        for q in exam['文字']:
            for i,o in enumerate(q['options']):
                if not forms(q,i,homophones):unmapped[o]+=1
    for year in sorted(data['exams']):
        reference_years=[y for y in sorted(data['exams']) if y!=year] if MODE=='leave-one-exam-out' else [y for y in sorted(data['exams']) if y<year]
        if MODE=='leave-one-exam-out':
            idx={}
            for reference_year in reference_years:learn(reference_year)
        assert all(w['year'] in reference_years for w in idx.values())
        qs=data['exams'][year]['文字']+data['exams'][year]['词汇']
        assert len(qs)==25
        for q in qs:
            g=q['groupNumber'];t=target(q);hit=known(t);ans=q['rightAnswer']-1
            if g==1:
                opts=[forms(q,i,homophones) for i in range(4)]
                hits=[bool(hit) if i==ans else any(known(f) for f in fs) for i,fs in enumerate(opts)]
                # Exact kana repetition only counts for confirmed real words,
                # not for an unclassified incorrect pronunciation.
                hits=[h or (i!=ans and bool(fs) and bool(known(q['options'][i]))) for i,(h,fs) in enumerate(zip(hits,opts))]
            elif g in (2,3):
                opts=[[o] for o in q['options']];hits=[bool(known(o)) for o in q['options']]
            else:opts=[];hits=[]
            k=sum(h for i,h in enumerate(hits) if i!=ans)
            if g==1:
                no_elimination=1.0 if hit else .25
                conditional=1.0 if hit else 1/(4-k)
            elif g==2:
                no_elimination=1.0 if hits[ans] else .25
                conditional=1.0 if hits[ans] else 1/(4-k)
            elif g==3:
                no_elimination=1.0 if hit and hits[ans] else .25
                conditional=(1.0 if hits[ans] else 1/(4-k)) if hit else .25
            else:
                no_elimination=conditional=1.0 if hit else .25
            rows.append({'year':year,'id':q['id'],'group':g,'number':q['number'],'target':t,'target_hit':bool(hit),'witness':hit,
                         'reference_years':reference_years,'reference_questions':25*len(reference_years),
                         'options':q['options'],'normalized_options':opts,'option_hits':hits,'known_distractors':k,
                         'no_elimination':no_elimination,'conditional_elimination':conditional,
                         'conditional_except_reading_elimination':no_elimination if g==1 else conditional})
        if MODE=='chronological':learn(year)
    summary={}
    for n in (len(data['exams']),10,6,4):
        years=sorted(data['exams'])[-n:];rs=[r for r in rows if r['year'] in years]
        def aggregate(rs):
            return {'n':len(rs),'target_hits':sum(r['target_hit'] for r in rs),'coverage':sum(r['target_hit'] for r in rs)/len(rs),
                    'no_elimination':sum(r['no_elimination'] for r in rs)/len(rs),
                    'conditional_elimination':sum(r['conditional_elimination'] for r in rs)/len(rs),
                    'conditional_except_reading_elimination':sum(r['conditional_except_reading_elimination'] for r in rs)/len(rs),
                    'elimination_helps_questions':sum(r['conditional_elimination']>r['no_elimination'] for r in rs)}
        summary[str(n)]={str(g):aggregate([r for r in rs if r['group']==g]) for g in (1,2,3,4)}
        summary[str(n)]['weighted_total']=aggregate(rs)
    return {'summary':summary,'rows':rows,'unclassified_or_ambiguous_reading_options':dict(unmapped)}

result={'scope':'Q1/Q3 marked target and all real-word options; Q2/Q4 option texts only. Cross-group shared history. No background stem words.',
        'evaluation_mode':MODE,
        'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'reading_mapping_sha256':hashlib.sha256((ROOT/'tools/reading_option_lexemes.tsv').read_bytes()).hexdigest(),
        'assumptions':['Known correct words are perfectly usable in context; Q4 known target gives perfect usage discrimination.',
                       'Q2 assumes enough understanding of the current context to discriminate familiar options; it does not learn vocabulary from stems.',
                       'Q3 elimination requires a familiar marked target.',
                       'Q1 conditional elimination assumes familiar wrong lexical alternatives can truly be ruled out; homophony means this is not guaranteed.',
                       'Uniform guessing among remaining alternatives; error-free elimination. Not measured learner accuracy.',
                       'Pseudoreadings and unmapped options do not count as independently learned words or eliminations.',
                       'Multiple proposed spellings for kana options are not evidence that all those words were intended in the original question. Two scenarios expose this sensitivity.'],
        'restricted_mapping':run(False),'common_homophone_expansion':run(True)}
(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
for mode in ('restricted_mapping','common_homophone_expansion'):
    print(mode)
    for n,summary in result[mode]['summary'].items():
        print(n,{g:{k:round(v,4) if isinstance(v,float) else v for k,v in a.items()} for g,a in summary.items()})
