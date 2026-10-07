const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(root, 'data.js'), 'utf8'), context);
context.window.ORDERING_FURIGANA = JSON.parse(fs.readFileSync(path.join(root, 'ordering-furigana.json'), 'utf8'));
vm.runInNewContext(fs.readFileSync(path.join(root, 'ordering-furigana.js'), 'utf8'), context);
const readings = context.window.ORDERING_FURIGANA;
const render = context.window.OrderingFurigana.render;
const escape = s => String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
let count = 0;
for (const categories of Object.values(context.window.EXAM_DATA.exams)) {
  for (const [category, questions] of Object.entries(categories)) for (const q of questions) {
    const eligible = category === '语法' && Number(q.groupNumber) === 5 && q.options.length === 4;
    if (!eligible) { assert(!readings[q.id]); continue; }
    count++;
    assert(readings[q.id], q.id);
    for (const text of [q.title, q.question, q.subQuestion, ...q.options].filter(Boolean)) {
      const tokens = readings[q.id][text];
      assert(tokens, `${q.id}: stale text`);
      assert.equal(tokens.map(t => t[0]).join(''), text);
      for (const [base, reading] of tokens) if (/[一-龯々]/.test(base)) assert.match(reading, /^[ぁ-ゖー]+$/);
      assert.equal(render(q.id, text, false, escape), escape(text));
      const html = render(q.id, text, true, escape);
      assert.equal(html.replace(/<rt>.*?<\/rt>/g, '').replace(/<\/?ruby[^>]*>/g, ''), escape(text));
    }
  }
}
assert.equal(Object.keys(readings).length, count);
const pairs = Object.values(readings).flatMap(entries => Object.values(entries).flat());
for (const [word, expected] of [['10万', 'じゅうまん'], ['先々週', 'せんせんしゅう'], ['850万', 'はっぴゃくごじゅうまん'], ['1000万', 'いっせんまん']]) {
  const found = pairs.filter(t => t[0] === word);
  assert(found.length > 0, word);
  assert(found.every(t => t[1] === expected), word);
}
assert.equal(render('missing', '<script>', true, escape), '&lt;script&gt;');
const id = Object.keys(readings)[0];
assert.equal(render(id, 'changed <text>', true, escape), 'changed &lt;text&gt;');
console.log(`PASS: ${count} grammar questions (problem 5 only), exact text preserved, full kanji coverage, visibility gate and escaping`);
