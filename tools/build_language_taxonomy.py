#!/usr/bin/env python3
"""Export agreed, problem-scoped language tags from explicit annotations.

Usage: python3 tools/build_language_taxonomy.py [--check]
Rebuilds only this knowledge-base section; never edits source exam answers.
"""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from language_tag_annotations import READING, MEANING, PARAPHRASE, USAGE

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/N1考试知识库/文字词汇分类'
SOURCE = ROOT / 'offline-exam-tool/data.js'
VERSION = '1.0'
# These annotations were reviewed against this exact bundle, not future changes.
REVIEWED_SOURCE_SHA256 = 'b3982d3045b36e02ddf9841f5da7ae81f6acdd65074abdfe9ce3c617d6b0189f'
GROUPS = {1:'读音', 2:'词汇意思', 3:'近义词替换', 4:'在句子中词汇用法'}
READ_CODES = {
 'V': ('verb', '动词读音'),
 'N': ('noun.onyomi', '名词与汉字熟语读音 / 二字熟语，通常是音读'),
 'K': ('noun.kunyomi', '名词与汉字熟语读音 / 训读名词'),
 'O': ('noun.other', '名词与汉字熟语读音 / 其他，如单字词、三字及以上熟语'),
 'I': ('adjective.i', '形容词读音 / い形容词'),
 'Y': ('adjective.yaka', '形容词读音 / ～やか结尾的な形容词'),
 'R': ('adjective.raka', '形容词读音 / ～らか结尾的な形容词'),
 'A': ('adjective.other', '形容词读音 / 其他な形容词'),
}
WORD_CODES = {
 'S': ('adjective.shii', '～しい结尾的形容词'),
 'J': ('adjective.other', '其他形容词、な形容词'),
 'C': ('verb.compound', '复合动词'),
 'V': ('verb.simple', '一般动词'),
 'H': ('kanji', '汉字熟语'),
 'K': ('katakana', '片假名词汇'),
 'M': ('mimetic.repeat', '拟声・拟态词 / ABAB重复型'),
 'T': ('mimetic.ri.sokuon', '拟声・拟态词 / ～り型 / 促音型'),
 'N': ('mimetic.ri.nasal', '拟声・拟态词 / ～り型 / 拨音型'),
 'R': ('mimetic.ri.other', '拟声・拟态词 / ～り型 / 其他'),
 'E': ('mimetic.other', '拟声・拟态词 / 其他形式'),
 'D': ('adverb', '一般副词'),
 'O': ('other', '其他名词及惯用表达'),
}
USE_CODES = {
 'S': ('sense', '核心词义与语境'),
 'O': ('object', '适用对象与使用范围'),
 'C': ('collocation', '固定搭配与惯用表达'),
 'B': ('boundary', '近义词的用法边界'),
 'E': ('evaluation', '褒贬色彩与感情色彩'),
 'R': ('register', '语体与使用场合'),
 'G': ('grammar', '词性与语法接续，作为辅助考点'),
}

SPECIAL_NOTES = {
 'sbry-n1-2010.12-文字・語彙-1-4': '「極めて」在此为副词。现有读音目录没有副词分支，本版依据其来自「極める」的读法暂归动词读音；保留原词「極めて」，并非判定句中词性为动词。',
 'sbry-n1-2014.07-文字・語彙-4-22': '原库答案为2，且原解析同样指定2；「心構えが決まらない」搭配与其他选项值得对照原始真题再核查。本次只标注词义辨析，不修订答案。',
 'sbry-n1-2021.07-文字・語彙-3-18': '原强调词为「スケ一ル」（汉字一），检索词规范为「スケール」；保留原始题干。',
 'markdown-2025.12-language-5': '原题强调范围为「芳しく」，正确选项含「ない」；归档到原形「芳しい」，原始强调范围与选项均保留。',
}

def clean(text):
    return re.sub(r'⟦/?u⟧|【|】', '', str(text)).strip()

def target(q, group):
    if group == 2:
        return q['options'][q['rightAnswer']-1]
    if group == 4:
        return clean(q['question'])
    matches = re.findall(r'⟦u⟧(.*?)⟦/u⟧|【([^】]+)】',q['question'])
    assert matches, f'Missing emphasized target: {q["id"]}'
    return ' / '.join(a or b for a,b in matches)

def parse_specs(text):
    result = {}
    for line in text.strip().splitlines():
        year, *tokens = line.split()
        assert year not in result
        result[year] = [(*token.split(':'), '') for token in tokens]
    return result

def parse_usage():
    result, year = {}, None
    for line in USAGE.strip().splitlines():
        if re.fullmatch(r'\d{4}\.\d{2}',line):
            year = line
            assert year not in result
            result[year] = []
        else:
            item, evidence = line.split(' ',1)
            lemma,codes = item.split(':')
            result[year].append((lemma,codes,evidence))
    return result

def definitions():
    result = []
    for group in GROUPS:
        codebook = READ_CODES if group==1 else USE_CODES if group==4 else WORD_CODES
        for code,(suffix,label) in codebook.items():
            if group==2 and code=='H':label='汉字熟语，以近义二字词辨析为主'
            if group==2 and code=='O':label='其他名词、惯用表达及构词成分'
            result.append({'id':f'language.q{group}.{suffix}', 'problemNumber':group,
                           'problemName':GROUPS[group], 'code':code, 'path':[GROUPS[group],*label.split(' / ')]})
    return result

def fingerprint(q):
    return hashlib.sha256(json.dumps(q,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def build_rows(data, tags):
    specs={1:parse_specs(READING),2:parse_specs(MEANING),3:parse_specs(PARAPHRASE),4:parse_usage()}
    tag_map={(t['problemNumber'],t['code']):t for t in tags}
    rows=[]
    for group in GROUPS:assert set(specs[group])==set(data['years'])
    for year in data['years']:
        for group in GROUPS:
            questions=[q for cat in ('文字','词汇') for q in data['exams'][year][cat] if q['groupNumber']==group]
            expected = 7 if group==2 else 6
            assert len(questions)==expected==len(specs[group][year]), (year,group)
            for ordinal,(q,(lemma,codes,evidence)) in enumerate(zip(questions,specs[group][year]),1):
                surface=target(q,group)
                if group==4:assert clean(lemma)==surface, (q['id'],lemma,surface)
                selected=[tag_map[group,c] for c in codes]
                assert selected and len(codes)==len(set(codes))
                if not evidence:
                    basis={1:'按题干强调词的读音及句中形式归类',2:'按本题正确选词归类，不按干扰项扩充标签',3:'按题干被替换词归类，不按替换答案的词类归类'}[group]
                    evidence=f'{basis}：「{surface}」归档为「{lemma}」；'+ '；'.join(' / '.join(t['path'][1:]) for t in selected)+'。'
                notes=[]
                if q['id'] in SPECIAL_NOTES:notes.append(SPECIAL_NOTES[q['id']])
                if year=='2024.12' and group==4:
                    notes.append('本期用法题源文本可见漏字、重复或接续转录异常；依据可辨识的考查对象标注，未校勘原文。')
                primary=selected[0]['id']
                if group==1 and 'K' in codes:primary=tag_map[group,'K']['id']
                row={'id':q['id'],'year':year,'subject':'文字・词汇','sourceCategory':'文字' if group==1 else '词汇',
                     'problemNumber':group,'problemName':GROUPS[group],'questionNumber':q['number'],
                     'questionOrdinalInProblem':ordinal,'surface':surface,'lemma':lemma,
                     'primaryTag':primary,'tags':[t['id'] for t in selected],
                     'tagPaths':[' / '.join(t['path']) for t in selected],
                     'evidence':evidence,'notes':notes,'taxonomyVersion':VERSION,
                     'annotationMethod':'Codex根据本地题干、选项逐题标注；非全量原卷校勘',
                     'sourceQuestionSha256':fingerprint(q),'sourceQuestion':q}
                if group==3:row['replacement']=q['options'][q['rightAnswer']-1]
                rows.append(row)
    return rows

def validate(rows,data,tags):
    expected={q['id']:q for e in data['exams'].values() for cat in ('文字','词汇') for q in e[cat]}
    actual={r['id']:r for r in rows}
    assert len(rows)==len(actual)==775
    assert set(actual)==set(expected),'Incomplete source coverage'
    tag_map={t['id']:t for t in tags}
    def check_scope(row):
        assert all(tag_map[t]['problemNumber']==row['problemNumber'] for t in row['tags']),row['id']
    for r in rows:
        assert r['tags'] and r['primaryTag'] in r['tags']
        assert len(r['tags'])==len(set(r['tags']))
        assert r['sourceQuestion']==expected[r['id']]
        assert r['sourceQuestionSha256']==fingerprint(expected[r['id']])
        assert r['problemNumber']==expected[r['id']]['groupNumber']
        check_scope(r)
        assert r['taxonomyVersion']==VERSION
        assert r['surface']==target(expected[r['id']],r['problemNumber'])
    # Behavioral regressions: noun/verb context, scope, and lexical boundary.
    assert actual['sbry-n1-2017.12-文字・語彙-1-6']['lemma']=='巡る'
    assert actual['markdown-2025.12-language-1']['tags']==['language.q1.noun.onyomi','language.q1.adjective.other']
    assert actual['sbry-n1-2015.07-文字・語彙-3-17']['tags']==['language.q3.kanji'] # 助言→アドバイス
    assert actual['markdown-2025.12-language-15']['tags']==['language.q3.adjective.other'] # ひそかに→こっそり
    assert actual['sbry-n1-2017.12-文字・語彙-2-13']['tags']==['language.q2.adjective.other'] # まちまち is not tagged by spelling alone
    # The scope guard itself must reject a valid tag from another problem.
    invalid={**rows[0], 'tags':['language.q4.sense']}
    try:
        check_scope(invalid)
    except AssertionError:
        pass
    else:
        raise AssertionError('Cross-problem tag was accepted')
    return {'status':'pass','sourceQuestions':len(expected),'taggedQuestions':len(rows),
            'untaggedQuestions':0,'duplicateIds':0,'outOfScopeTags':0,
            'multiTagQuestions':sum(len(r['tags'])>1 for r in rows),
            'questionsWithNotes':sum(bool(r['notes']) for r in rows),
            'problemCounts':dict(Counter(str(r['problemNumber']) for r in rows)),
            'checks':['全量ID一一对应','每题至少一个标签','标签仅来自所属问题','原题与答案保持一致',
                      '原形和替换对象边界回归','分类版本一致','文档链接与锚点有效']}

def esc(value):
    return re.sub(r'\s+',' ',str(value)).replace('|','\\|').replace('<','&lt;').replace('>','&gt;')

def anchor(r):return 'q-'+str(r['problemNumber'])+'-'+str(r['questionOrdinalInProblem'])

def question_link(r,prefix=''):
    return f'[{r["year"]} 問題{r["problemNumber"]}-{r["questionOrdinalInProblem"]}]({prefix}期次/{r["year"]}.md#{anchor(r)})'

def render(data,tags,rows,report):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'期次').mkdir(exist_ok=True)
    (OUT/'标签').mkdir(exist_ok=True)
    (OUT/'校验报告.json').write_text('{"status":"checking"}\n',encoding='utf-8')
    tag_map={t['id']:t for t in tags}
    taxonomy={'version':VERSION,'agreedDate':'2026-09-20','subject':'文字・词汇',
              'scope':'問題1—4；题库底层文字与词汇合并，不含语法、阅读、听力',
              'rules':['一题可多标签','标签problemNumber必须等于原题groupNumber','按原形归档并保留题面形式',
                       '問題2按正确选词；問題3按题干被替换词；問題4按四个句子的用法差别',
                       '主标签是本题主要归档入口；辅助标签仍不得跨问题'], 'tags':tags}
    (OUT/'分类法.json').write_text(json.dumps(taxonomy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 文字・词汇考点分类法', '', '版本：1.0；商定日期：2026-09-20。', '',
           '适用范围：31期离线真题的文字・词汇（問題1—4）。本目录是此前跨科目草稿在文字・词汇范围内的正式替代。', '',
           '## 标签规则', '', *['- '+x for x in taxonomy['rules']], '',
           '## 分类边界', '',
           '- 汉字熟语按词汇书写及构词组织，不限定名词或纯音读；如「頑丈」可同时标二字熟语和其他な形容词。',
           '- 读音中的其他名词与熟语包括混合读法，如「指図、相場、跡地、手際、本筋」。',
           '- 「～やか／～らか」指な形容词词干；い形容词活用还原到原形。',
           '- 「～しい」按原形词尾判定；「すさまじい」放其他形容词，不因意思相近强并入。',
           '- 复合动词与一般动词分开；动词派生但在本题作名词的「見返り、手分け、意気込み」按名词归档。',
           '- 拟声拟态词须先判断词汇性质，再分词形；不能只见重复或り结尾就归入。「まちまち」归其他な形容词，「てっきり、しきりに」归一般副词。',
           '- ABAB允许常见清浊变化重复形式「つくづく」；「むしゃくしゃ、ぎくしゃく、てきぱき」归其他形式。',
           '- 用法题的语法接续只作辅助标签；不会因为题中出现动词就借用問題1—3的动词标签。',
           '- 边界例外：「極めて」实际为副词，暂按动词来源归到读音的动词类，逐题注明，不新增未经商定的标签。', '',]
    for group,title in GROUPS.items():
        lines += [f'## {title}（問題{group}）','']
        for t in tags:
            if t['problemNumber']==group:lines += [f'- {" / ".join(t["path"][1:])}：`{t["id"]}`']
        lines += ['']
    (OUT/'分类法.md').write_text('\n'.join(lines),encoding='utf-8')
    (OUT/'题目标签.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    # Small sidecar for future consumers; keys attach to existing stable IDs.
    overlay={r['id']:{k:r[k] for k in ('problemNumber','lemma','primaryTag','tags','evidence','notes','sourceQuestionSha256')} for r in rows}
    (OUT/'标签映射.json').write_text(json.dumps({'taxonomyVersion':VERSION,'sourceSha256':REVIEWED_SOURCE_SHA256,'questions':overlay},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for year in data['years']:
        lines=[f'# {year} 文字・词汇题目标签','', '[返回目录](../README.md)','', '题干、选项、答案均保留本地题库原文；分类不构成对原始真题的重新校勘。','']
        for r in (r for r in rows if r['year']==year):
            q=r['sourceQuestion']
            lines += [f'<a id="{anchor(r)}"></a>',f'## 問題{r["problemNumber"]}-{r["questionOrdinalInProblem"]} · {r["lemma"]}','',
                      f'原题号：{r["questionNumber"]}；ID：`{r["id"]}`','',
                      '标签：'+'；'.join(f'[{" / ".join(tag_map[t]["path"])}](../标签/{t}.md)' for t in r['tags']),'',
                      '分类依据：'+r['evidence'],'', '题面词：'+r['surface']+'；归档词：'+r['lemma'],'']
            if 'replacement' in r:lines += ['近义替换：'+r['replacement'],'']
            lines += ['备注：'+note for note in r['notes']]
            lines += ['',q['question'],'']
            lines += [f'{n}. {option}' for n,option in enumerate(q['options'],1)]
            lines += ['',f'原题库答案：{q["rightAnswer"]}','']
        (OUT/'期次'/f'{year}.md').write_text('\n'.join(lines),encoding='utf-8')
    def table(rs,prefix=''):
        result=['| 题目 | 题面词 → 归档词 | 标签 | 依据 |','|---|---|---|---|']
        for r in rs:
            result.append(f'| {question_link(r,prefix)} | {esc(r["surface"])} → {r["lemma"]} | '+ '；'.join(' / '.join(tag_map[t]['path'][1:]) for t in r['tags'])+f' | {esc(r["evidence"])} |')
        return result
    for group,title in GROUPS.items():
        (OUT/f'問題{group}-{title}.md').write_text('\n'.join([f'# {title}','', '[返回目录](README.md)','', *table([r for r in rows if r['problemNumber']==group])])+'\n',encoding='utf-8')
    for tag in tags:
        matching=[r for r in rows if tag['id'] in r['tags']]
        (OUT/'标签'/f'{tag["id"]}.md').write_text('\n'.join([f'# {" / ".join(tag["path"])}','', '[返回目录](../README.md)','',f'共 {len(matching)} 道；本页所有题都属于問題{tag["problemNumber"]}。','',*table(matching,'../')])+'\n',encoding='utf-8')
    lines=['# 文字・词汇分类知识库','', f'已为 **31期、775道题** 全量标注；每题仅使用所属问题的标签，可多选。分类版本 {VERSION}。','',
           '- [分类法](分类法.md) · [机器可读分类法](分类法.json)',
           '- [全量逐题标签与原题快照](题目标签.jsonl) · [按题目ID关联的标签映射](标签映射.json)',
           '- [校验报告](校验报告.json) · [分类边界与原题核查备注](核查备注.md)','',
           '## 按问题查看','', '| 问题 | 题数 |','|---|---:|']
    lines += [f'| [問題{g} · {title}](問題{g}-{title}.md) | {report["problemCounts"][str(g)]} |' for g,title in GROUPS.items()]
    lines += ['', '## 按标签查看','', '| 问题 | 标签 | 题数 |','|---|---|---:|']
    counts=Counter(t for r in rows for t in r['tags'])
    lines += [f'| 問題{t["problemNumber"]} | [{" / ".join(t["path"][1:])}](标签/{t["id"]}.md) | {counts[t["id"]]} |' for t in tags]
    lines += ['', '多标签计数不可直接相加作为题目总数。','', '## 按期次查看','', *[f'- [{y}](期次/{y}.md)' for y in data['years']], '',
              '## 维护与来源','',
              '以 `offline-exam-tool/data.js` 中的文字、词汇为完整源集合，保留原题ID。标注表维护在 `tools/language_tag_annotations.py`，生成和校验入口是 `python3 tools/build_language_taxonomy.py`；只检查可加 `--check`。',
              '源题库哈希固定，源数据改变后必须重新核对相关标注，再更新脚本中的源版本；避免按位置静默错配。',
              '此处是知识库标签附件，尚未改变答题网页显示。原题答案、原解析和个人作答记录不变。', '']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    lines=['# 分类边界与原题核查备注','', '[返回目录](README.md)','', '以下题目已有分类；备注说明边界约定或源数据问题，并不表示已修改原题答案。','']
    for r in rows:
        for note in r['notes']:lines += [f'- {question_link(r)}：{note}']
    (OUT/'核查备注.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def validate_links():
    for path in OUT.rglob('*.md'):
        for href in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            filename,_,fragment=href.partition('#')
            dest=path.parent/filename
            assert dest.is_file(),(path,href)
            if fragment:assert f'id="{fragment}"' in dest.read_text(encoding='utf-8'),(path,href)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    raw=SOURCE.read_text(encoding='utf-8')
    assert hashlib.sha256(raw.encode()).hexdigest()==REVIEWED_SOURCE_SHA256,'Source changed; re-review annotations first'
    data=json.loads(raw.split('=',1)[1].rstrip(';\n'))
    tags=definitions()
    rows=build_rows(data,tags)
    report=validate(rows,data,tags)
    if not args.check:
        render(data,tags,rows,report)
    else:
        saved=[json.loads(line) for line in (OUT/'题目标签.jsonl').read_text(encoding='utf-8').splitlines()]
        assert saved==rows,'Generated annotations are stale'
        assert json.loads((OUT/'分类法.json').read_text(encoding='utf-8'))['tags']==tags
        mapping=json.loads((OUT/'标签映射.json').read_text(encoding='utf-8'))
        assert set(mapping['questions'])=={r['id'] for r in rows}
        assert mapping['sourceSha256']==REVIEWED_SOURCE_SHA256
        assert mapping['taxonomyVersion']==VERSION
        for row in rows:
            assert mapping['questions'][row['id']]=={k:row[k] for k in ('problemNumber','lemma','primaryTag','tags','evidence','notes','sourceQuestionSha256')}
        assert json.loads((OUT/'校验报告.json').read_text(encoding='utf-8'))==report
    validate_links()
    if not args.check:
        (OUT/'校验报告.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
