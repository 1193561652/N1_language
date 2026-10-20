"""Generate offline readings for grammar sentence questions and all reading questions.

Optional maintenance dependencies: requirements-furigana.txt. Normal exam builds
use the checked-in JSON and do not need a tokenizer or network connection.
"""
import json
import re
from pathlib import Path
from sudachipy import dictionary, tokenizer

ROOT = Path(__file__).resolve().parent
KANJI = re.compile(r"[一-龯々]")
# Context-reviewed corrections. Preserve the source spelling and punctuation.
OVERRIDES = {'10万': 'じゅうまん', '15万': 'じゅうごまん', '一歩': 'いっぽ',
             '一晩': 'ひとばん', '近々': 'ちかぢか', '北市': 'きたし',
             '850万': 'はっぴゃくごじゅうまん', '1000万': 'いっせんまん',
             '先々週': 'せんせんしゅう'}


# OCR variants: readings follow the surrounding Japanese; source text stays intact.
OCR_READINGS = {'增': 'ふ', '问': 'もん', '携帶': 'けいたい', '责任': 'せきにん',
                '厶': 'む', '述': 'の', '滅': 'ほろ', '滅少': 'げんしょう',
                '剩': 'じょう', '赘沢': 'ぜいたく', '费者': 'ひしゃ', '查書': 'さしょ',
                '杈': 'のり', '尐数': 'しょうすう', '窗体': 'そうたい', '侵人': 'しんにゅう',
                '募': 'ぼ', '激': 'げき', '吞': 'の', '踏': 'とう', '励金': 'れいきん'}


def hiragana(text):
    return ''.join(chr(ord(c) - 0x60) if '\u30a1' <= c <= '\u30f6' else c for c in text)


def split_reading(surface, reading):
    # Keep inflection kana on the baseline: 食べる -> 食(た) + べる.
    parts = re.findall(r'[一-龯々]+|[^一-龯々]+', surface)
    pattern = ''.join('(.+?)' if KANJI.search(p) else re.escape(hiragana(p)) for p in parts)
    match = re.fullmatch(pattern, reading)
    if not match:
        return [[surface, reading]]
    readings = iter(match.groups())
    return [[p, next(readings)] if KANJI.search(p) else [p] for p in parts]


def build():
    raw = (ROOT / 'data.js').read_text(encoding='utf-8')
    data = json.loads(raw[raw.index('{'):].strip().rstrip(';'))
    engine = dictionary.Dictionary().tokenizer()
    output, unknown = {}, []
    for categories in data['exams'].values():
        for q in categories.get('语法', []) + categories.get('阅读', []):
            if q not in categories.get('阅读', []) and (int(q['groupNumber']) != 5 or len(q['options']) != 4):
                continue
            entries = {}
            for text in [q.get(k, '') for k in ('groupTitle', 'passage', 'title', 'question', 'subQuestion')] + q['options']:
                if not text:
                    continue
                tokens = []
                protected = re.compile(r'[一-龯々]+\([ぁ-ゖ]+\)|' + '|'.join(map(re.escape, OVERRIDES)))
                chunks, pos = [], 0
                for match in protected.finditer(text):
                    chunks.extend((text[pos:match.start()], match.group()))
                    pos = match.end()
                chunks.append(text[pos:])
                for chunk in chunks:
                    explicit = re.fullmatch(r'([一-龯々]+)\(([ぁ-ゖ]+)\)', chunk)
                    if explicit:
                        tokens.extend([[explicit[1], explicit[2]], ['(' + explicit[2] + ')']])
                        continue
                    if chunk in OVERRIDES:
                        tokens.append([chunk, OVERRIDES[chunk]])
                        continue
                    for m in engine.tokenize(chunk, tokenizer.Tokenizer.SplitMode.C):
                        surface, reading = m.surface(), hiragana(m.reading_form())
                        if surface == '関' and '医療機\n関' in text:
                            reading = 'かん'
                        if surface == '君' and q['id'] == 'sbry-n1-2012.12-文法-5-28':
                            reading = 'きみ'
                        if KANJI.search(surface):
                            if not re.fullmatch(r'[ぁ-ゖー]+', reading):
                                reading = ('しょう' if chunk[max(0, m.begin()-1):m.begin()] == '減' else 'すく') if surface == '尐' else OCR_READINGS.get(surface, reading)
                            if not re.fullmatch(r'[ぁ-ゖー]+', reading):
                                unknown.append([q['id'], surface, chunk[max(0, m.begin()-15):m.end()+15]])
                                tokens.append([surface])
                            else:
                                tokens.extend(split_reading(surface, reading))
                        else:
                            tokens.append([surface])
                merged = []
                for token in tokens:
                    if len(token) == 1 and merged and len(merged[-1]) == 1:
                        merged[-1][0] += token[0]
                    else:
                        merged.append(token)
                assert ''.join(t[0] for t in merged) == text
                entries[text] = merged
            output[q['id']] = entries
    if unknown:
        raise ValueError(f'Missing readings: {unknown}')
    (ROOT / 'ordering-furigana.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Generated readings for {len(output)} questions')


if __name__ == '__main__':
    build()
