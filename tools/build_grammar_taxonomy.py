#!/usr/bin/env python3
"""Build the agreed grammar taxonomy and only its latest-ten-period annotations.

python3 tools/build_grammar_taxonomy.py [--check]
The source bundle must match the reviewed version. Original questions, answers,
web UI, and learner history are never modified by this command.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from grammar_tag_annotations import SENTENCE, ORDERING, DISCOURSE, NOTES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/N1考试知识库/语法分类'
SOURCE = ROOT / 'offline-exam-tool/data.js'
SOURCE_SHA = 'b3982d3045b36e02ddf9841f5da7ae81f6acdd65074abdfe9ce3c617d6b0189f'
YEARS = ['2025.12','2025.07','2024.12','2024.07','2023.12','2023.07','2022.12','2022.07','2021.12','2021.07']
GROUPS = {5:'句子语法',6:'句子排序',7:'篇章语法'}
BOOK_URL = 'https://www.3anet.co.jp/np/books/3600/'
BOOK_CHAPTERS = {
 5: ['时间关系','范围的起点与界限','限定、非限定与追加','举例','关联与无关','状态','伴随行为',
     '逆接','条件','逆接条件','目的与手段','原因与理由','可能、不可能与禁止','话题与评价标准',
     '比较与对照','结局与最终状态','强调','主张与断定','评价与感想','心情与不由自主的感受'],
 6: ['句子组装——固定形式','句子组装——修饰名词的形式','句子组装——注意接续'],
 7: ['时制','表示条件的句子','保持视点——动词用法与自他动词','保持视点——「～てくる／～ていく」',
     '保持视点——被动、使役与使役被动','保持视点——「～てあげる／～てもらう／～てくれる」',
     '指示表达「こ・そ・あ」','「は／が」的区别','接续表达','省略、重复与换言','文体一致性','话语流程'],
}
SUPPLEMENTS = ['助词与固定搭配','词性、活用与接续','敬语与授受','自他动词、被动与使役','时制与体','推测、意志、说明等表达']

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def taxonomy():
    tags=[]
    for group,names in BOOK_CHAPTERS.items():
        for i,name in enumerate(names,1):
            tags.append({'id':f'grammar.q{group}.c{i:02}', 'code':f'c{i:02}',
                         'problemNumber':group,'problemName':GROUPS[group],'name':name,
                         'path':[GROUPS[group],name],'origin':'textbook',
                         'textbookPart':group-4,'textbookChapter':i,
                         'locator':f'第{group-4}部—第{i}课','sourceUrl':BOOK_URL})
        if group==5:
            for i,name in enumerate(SUPPLEMENTS,1):
                tags.append({'id':f'grammar.q5.b{i:02}', 'code':f'b{i:02}',
                             'problemNumber':5,'problemName':GROUPS[5],'name':name,
                             'path':[GROUPS[5],'基础语法（真题补充）',name],
                             'origin':'agreedSupplement','locator':None})
    assert len(tags)==41
    return {'version':'1.0','agreedDate':'2026-09-20','subject':'语法',
            'textbook':'新完全マスター文法 日本語能力試験N1','textbookSource':BOOK_URL,
            'periods':YEARS,'textbookCategoryCount':35,'supplementCategoryCount':6,
            'excludedTextbookSection':'第1部Ⅳ：语法形式整理，仅辅助查阅，不作为分类',
            'rules':['只标注2021.07—2025.12最近10期，其他期次不生成正式标签',
                     '一题可以多标签，标签只来自本题所属問題5、6或7',
                     '第一个标签为主标签，其余为辅助标签；具体句型单独记录',
                     '教材标签为章节能力映射，不自动宣称具体句型是该章精确条目',
                     '基础语法6类为商定补充，不冒充教材原目录',
                     '篇章题结合共享全文；排序题考查整个句子结构，不只看星号答案',
                     '疑似转录或答案问题单独备注，保留原题和原答案'], 'tags':tags}

def parse(text):
    result={}
    year=None
    for line in text.strip().splitlines():
        if re.fullmatch(r'\d{4}\.\d{2}',line):
            year=line
            assert year not in result
            result[year]=[]
        else:
            codes,construction,evidence=[v.strip() for v in line.split('|',2)]
            result[year].append({'codes':codes.split(','),'construction':construction,'evidence':evidence})
    assert set(result)==set(YEARS)
    return result

def source_questions(data,year,group):
    return [q for q in data['exams'][year]['语法'] if q['groupNumber']==group]

def collect(data,tax):
    specs={5:parse(SENTENCE),6:parse(ORDERING),7:parse(DISCOURSE)}
    tags={t['id']:t for t in tax['tags']}
    rows=[]
    for year in YEARS:
        article_q=source_questions(data,year,7)[0]
        article=article_q.get('passage') or article_q['question']
        assert len(article)>100,(year,'Missing article')
        for group in GROUPS:
            qs=source_questions(data,year,group)
            assert len(qs)==len(specs[group][year])=={5:10,6:5,7:4}[group]
            for ordinal,(q,spec) in enumerate(zip(qs,specs[group][year]),1):
                selected=[f'grammar.q{group}.{code}' for code in spec['codes']]
                row={'id':q['id'],'year':year,'subject':'语法','problemNumber':group,'problemName':GROUPS[group],
                     'questionNumber':q['number'],'questionOrdinalInProblem':ordinal,
                     'primaryTag':selected[0],'tags':selected,
                     'tagPaths':[' / '.join(tags[t]['path']) for t in selected],
                     'construction':spec['construction'],'evidence':spec['evidence'],
                     'mappingLevel':'章节能力映射／商定补充；非教材精确条目断言',
                     'notes':[NOTES[q['id']]] if q['id'] in NOTES else [],
                     'annotationMethod':'Codex逐题核对题干、选项；篇章题参照全文',
                     'taxonomyVersion':tax['version'],'sourceQuestionSha256':digest(q),'sourceQuestion':q}
                if group==7:
                    row['sharedPassage']={'sourceQuestionId':article_q['id'],'text':article,'sha256':digest(article)}
                rows.append(row)
    return rows

def check_scope(row,tags):
    if row['year'] not in YEARS:
        raise ValueError('Period outside latest-ten scope')
    if not row['tags'] or any(t not in tags or tags[t]['problemNumber']!=row['problemNumber'] for t in row['tags']):
        raise ValueError('Invalid or cross-problem tag')

def validate(data,tax,rows):
    tags={t['id']:t for t in tax['tags']}
    assert len(tags)==41
    expected={q['id']:q for year in YEARS for q in data['exams'][year]['语法']}
    assert len(rows)==len(expected)==len({r['id'] for r in rows})==190
    assert {r['id'] for r in rows}==set(expected)
    assert set(NOTES)<=set(expected)
    for r in rows:
        check_scope(r,tags)
        assert len(r['tags'])==len(set(r['tags']))
        assert r['primaryTag'] in r['tags']
        assert r['sourceQuestion']==expected[r['id']]
        assert r['sourceQuestionSha256']==digest(expected[r['id']])
        assert r['problemNumber']==expected[r['id']]['groupNumber']
        assert r['taxonomyVersion']==tax['version']
        assert r['construction'] and r['evidence']
        if r['problemNumber']==7:
            first=source_questions(data,r['year'],7)[0]
            text=first.get('passage') or first['question']
            assert r['sharedPassage']=={'sourceQuestionId':first['id'],'text':text,'sha256':digest(text)}
    for invalid in ({**rows[0],'tags':['grammar.q7.c01']},{**rows[0],'year':'2020.12'}):
        try:check_scope(invalid,tags)
        except ValueError:pass
        else:raise AssertionError('Scope guard accepted invalid annotation')
    by_id={r['id']:r for r in rows}
    assert 'grammar.q5.b03' in by_id['jlpt4you-2023.07-grammar-5-8']['tags']
    assert 'grammar.q5.b01' in by_id['jlpt4you-2023.07-grammar-5-1']['tags']
    assert all(t.startswith('grammar.q6.') for t in by_id['sbry-n1-2021.07-文法-6-36']['tags'])
    assert by_id['jlpt4you-2023.07-grammar-7-1']['notes']
    return {'status':'pass','periods':YEARS,'taggedQuestions':len(rows),'untaggedQuestions':0,
            'outOfScopePeriods':0,'outOfScopeTags':0,'duplicateIds':0,
            'problemCounts':dict(Counter(str(r['problemNumber']) for r in rows)),
            'multiTagQuestions':sum(len(r['tags'])>1 for r in rows),
            'questionsWithNotes':sum(bool(r['notes']) for r in rows),
            'textbookCategories':35,'supplementCategories':6,
            'checks':['最近10期全量ID对应','排除更早期次','每题有标签且标签不跨问题','跨问题和超期次反例被拒绝',
                      '原题和答案一致','全部篇章题关联全文','具体结构及依据非空','疑点保留','文件链接与锚点有效']}

def esc(text):
    return re.sub(r'\s+',' ',str(text)).replace('|','\\|').replace('<','&lt;').replace('>','&gt;')

def anchor(row):return f'q-{row["problemNumber"]}-{row["questionOrdinalInProblem"]}'

def question_link(row,prefix=''):
    return f'[{row["year"]} 問題{row["problemNumber"]}-{row["questionOrdinalInProblem"]}]({prefix}期次/{row["year"]}.md#{anchor(row)})'

def overlay(rows):
    return {'taxonomyVersion':'1.0','periods':YEARS,'sourceSha256':SOURCE_SHA,
            'questions':{r['id']:{k:r[k] for k in ('problemNumber','construction','primaryTag','tags','evidence','notes','sourceQuestionSha256')} for r in rows}}

def render(tax,rows,report):
    OUT.mkdir(parents=True,exist_ok=True)
    for sub in ('期次','标签'):(OUT/sub).mkdir(exist_ok=True)
    (OUT/'校验报告.json').write_text('{"status":"checking"}\n',encoding='utf-8')
    (OUT/'分类法.json').write_text(json.dumps(tax,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'题目标签.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    (OUT/'标签映射.json').write_text(json.dumps(overlay(rows),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tags={t['id']:t for t in tax['tags']}
    lines=['# 语法考点分类法','', '版本1.0；商定日期：2026-09-20。','',
           f'教材：[《新完全マスター文法 日本語能力試験N1》出版社目录]({BOOK_URL})。类别名称为分类用中文译名。','',
           '**35个教材章节类别＋6个真题补充类别，共41类。** 不将第1部Ⅳ“语法形式整理”设为分类。','',
           '## 标注规则','', *['- '+r for r in tax['rules']],'',
           '教材章节标签用于组织相应能力的真题；与同名教材课有能力联系，不等于每个句型都属于该课目录中的精确条目。具体句型另存construction字段。','']
    for g,name in GROUPS.items():
        lines += [f'## {name}（問題{g}）','',f'对应教材第{g-4}部。','']
        for i,label in enumerate(BOOK_CHAPTERS[g],1):lines += [f'{i}. {label}']
        lines += ['']
        if g==5:
            lines += ['### 基础语法（真题补充）','', *[f'{i}. {label}' for i,label in enumerate(SUPPLEMENTS,1)],'']
    (OUT/'分类法.md').write_text('\n'.join(lines),encoding='utf-8')
    def table(items,prefix=''):
        result=['| 题目 | 具体结构 | 标签 | 分类依据 |','|---|---|---|---|']
        for r in items:
            labels='；'.join(tags[t]['name'] for t in r['tags'])
            result.append(f'| {question_link(r,prefix)} | {esc(r["construction"])} | {labels} | {esc(r["evidence"])} |')
        return result
    for year in YEARS:
        items=[r for r in rows if r['year']==year]
        article=next(r['sharedPassage']['text'] for r in items if r['problemNumber']==7)
        lines=[f'# {year} 语法题目标签','', '[返回目录](../README.md)','',
               '题干、选项、答案保留原题库记录；疑点见备注。分類标签与正确答案校勘是不同工作。','']
        for r in items:
            q=r['sourceQuestion']
            lines += [f'<a id="{anchor(r)}"></a>',f'## 問題{r["problemNumber"]}-{r["questionOrdinalInProblem"]} · {r["construction"]}','',
                      f'原题号：{r["questionNumber"]}；ID：`{r["id"]}`','',
                      '主标签：'+tags[r['primaryTag']]['name'],'',
                      '全部标签：'+'；'.join(f'[{" / ".join(tags[t]["path"])}](../标签/{t}.md)' for t in r['tags']),'',
                      '分类依据：'+r['evidence'],'',*['备注：'+note for note in r['notes']],'']
            if r['problemNumber']==7:lines += ['[查看本组共享文章](#shared-passage)','']
            lines += [q['question'],'', *[f'{i}. {o}' for i,o in enumerate(q['options'],1)],'',f'原题库答案：{q["rightAnswer"]}','']
        lines += ['<a id="shared-passage"></a>','## 問題7共享全文','',article,'']
        (OUT/'期次'/f'{year}.md').write_text('\n'.join(lines),encoding='utf-8')
    for g,name in GROUPS.items():
        (OUT/f'問題{g}-{name}.md').write_text('\n'.join([f'# {name}','', '[返回目录](README.md)','',*table([r for r in rows if r['problemNumber']==g])])+'\n',encoding='utf-8')
    for tag in tax['tags']:
        items=[r for r in rows if tag['id'] in r['tags']]
        description=tag['locator'] if tag['origin']=='textbook' else '真题补充，不是教材原目录'
        (OUT/'标签'/f'{tag["id"]}.md').write_text('\n'.join([f'# {" / ".join(tag["path"])}','', '[返回目录](../README.md)','',
                   f'{description}；共{len(items)}题，均属于問題{tag["problemNumber"]}。','',*table(items,'../')])+'\n',encoding='utf-8')
    lines=['# 语法分类知识库','', '**最近10期（2021.07—2025.12）190道语法题已标注。** 只使用本题所属问题的标签，每题可多选。','',
           '- [商定分类法](分类法.md) · [机器可读分类法](分类法.json)',
           '- [全量逐题标签与原题](题目标签.jsonl) · [按ID关联标签](标签映射.json)',
           '- [校验报告](校验报告.json) · [源题疑点备注](核查备注.md)','',
           '## 按问题查看','', '| 问题 | 题数 | 类别数 |','|---|---:|---:|']
    lines += [f'| [問題{g} · {name}](問題{g}-{name}.md) | {report["problemCounts"][str(g)]} | {sum(t["problemNumber"]==g for t in tax["tags"])} |' for g,name in GROUPS.items()]
    lines += ['', '## 按标签查看','', '| 问题 | 类别 | 来源 | 题数 |','|---|---|---|---:|']
    counts=Counter(t for r in rows for t in r['tags'])
    lines += [f'| 問題{t["problemNumber"]} | [{t["name"]}](标签/{t["id"]}.md) | {t["locator"] or "真题补充"} | {counts[t["id"]]} |' for t in tax['tags']]
    lines += ['', '多标签题会出现在多个索引中，类别题数不可直接相加。','', '## 按期次查看','', *[f'- [{year}](期次/{year}.md)' for year in YEARS],'',
              '## 维护','', '显式逐题标注位于 `tools/grammar_tag_annotations.py`。运行 `python3 tools/build_grammar_taxonomy.py` 生成，追加 `--check` 只读校验。',
              '源题库指纹固定；更新题库后需要复核标注和期次范围，不会悄悄为新增或更早期次套用标签。每条标签保存分类依据，篇章题带全文。',
              '此处为本地知识库标签附件，尚未改变网页显示；原始答案与个人作答记录不变。','']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    lines=['# 源题疑点备注','', '[返回目录](README.md)','', '这些题仍已按可辨认的考点标注；未以本次分类工作替代原卷校勘，未修改原答案。','']
    lines += [f'- {question_link(r)}：{note}' for r in rows for note in r['notes']]
    (OUT/'核查备注.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def check_links():
    assert {p.stem for p in (OUT/'期次').glob('*.md')}==set(YEARS)
    for path in OUT.rglob('*.md'):
        for href in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if href.startswith('https://'):continue
            name,_,fragment=href.partition('#')
            dest=path.parent/name if name else path
            assert dest.is_file(),(path,href)
            if fragment:assert f'id="{fragment}"' in dest.read_text(encoding='utf-8'),(path,href)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    raw=SOURCE.read_text(encoding='utf-8')
    assert hashlib.sha256(raw.encode()).hexdigest()==SOURCE_SHA,'Source changed: re-review first'
    data=json.loads(raw.split('=',1)[1].rstrip(';\n'))
    assert sorted(data['years'],reverse=True)[:10]==YEARS
    tax=taxonomy()
    rows=collect(data,tax)
    report=validate(data,tax,rows)
    if args.check:
        assert [json.loads(line) for line in (OUT/'题目标签.jsonl').read_text(encoding='utf-8').splitlines()]==rows
        assert json.loads((OUT/'分类法.json').read_text(encoding='utf-8'))==tax
        assert json.loads((OUT/'标签映射.json').read_text(encoding='utf-8'))==overlay(rows)
        assert json.loads((OUT/'校验报告.json').read_text(encoding='utf-8'))==report
    else:render(tax,rows,report)
    check_links()
    if not args.check:(OUT/'校验报告.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
