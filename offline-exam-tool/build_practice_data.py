"""Join reviewed, problem-scoped annotations to the current original exams.

Keep this metadata separate from data.js so adding practice features never
changes the source bundle fingerprints used by annotation review tools.
"""
import hashlib
import json
from pathlib import Path


def build_practice_data(data, root):
    questions = {}
    for year, exam in data['exams'].items():
        for category, items in exam.items():
            for q in items:
                if q['id'] in questions:
                    raise ValueError(f"Duplicate question ID: {q['id']}")
                questions[q['id']] = (year, category, q)
    result = {'version': 1, 'subjects': [], 'tags': [], 'questions': {}}
    for folder, subject, categories in [
        ('文字词汇分类', '文字・词汇', {'文字', '词汇'}),
        ('语法分类', '语法', {'语法'}),
    ]:
        directory = Path(root) / 'output' / 'N1考试知识库' / folder
        taxonomy = json.loads((directory / '分类法.json').read_text(encoding='utf-8'))
        mapping = json.loads((directory / '标签映射.json').read_text(encoding='utf-8'))
        result['subjects'].append(subject)
        tags = {t['id']: t for t in taxonomy['tags']}
        for tag in tags.values():
            result['tags'].append({
                'id': tag['id'], 'subject': subject,
                'problemNumber': tag['problemNumber'], 'problemName': tag['problemName'],
                'name': ' / '.join(tag['path'][1:]) or tag.get('name', tag['id']),
            })
        for qid, annotation in mapping['questions'].items():
            if qid not in questions:
                raise ValueError(f'Annotation references missing question: {qid}')
            year, category, q = questions[qid]
            selected = list(dict.fromkeys(annotation.get('tags', [])))
            if not selected:
                continue
            fingerprint = hashlib.sha256(json.dumps(q, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if fingerprint != annotation['sourceQuestionSha256']:
                raise ValueError(f'Annotated question changed; re-review before rebuilding: {qid}')
            if category not in categories or annotation['problemNumber'] != q['groupNumber']:
                raise ValueError(f'Annotation subject/problem mismatch: {qid}')
            for tid in selected:
                if tid not in tags or tags[tid]['problemNumber'] != q['groupNumber']:
                    raise ValueError(f'Invalid or cross-problem tag: {qid}: {tid}')
            meta = {'year': year, 'category': category, 'subject': subject,
                    'problemNumber': q['groupNumber'], 'tags': selected}
            # A randomly selected later blank must carry its full source article.
            if category == '语法' and q['groupNumber'] == 7:
                group = [item for item in data['exams'][year][category] if item['groupNumber'] == 7]
                first = group[0]
                article = q.get('passage') or first.get('passage') or first.get('question', '')
                if len(article) < 100:
                    raise ValueError(f'Missing shared grammar article: {qid}')
                meta['sharedPassage'] = article
            result['questions'][qid] = meta
    return result
