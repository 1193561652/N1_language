// Run: node offline-exam-tool/tests/test_special_practice.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const dir = path.resolve(__dirname, '..');
const context = vm.createContext({ window: {} });
for (const name of ['data.js', 'practice-data.js', 'special-practice.js']) {
  vm.runInContext(fs.readFileSync(path.join(dir, name), 'utf8'), context);
}
const { EXAM_DATA: data, PRACTICE_DATA: catalog, SpecialPractice } = context.window;
const practice = SpecialPractice.create(data, catalog);
assert.equal(practice.pool.length, Object.keys(catalog.questions).length);
assert(practice.pool.length > 0);
for (const subject of practice.subjects) {
  const ids = practice.eligible({ subject });
  assert(ids.length);
  assert(ids.every((id) => catalog.questions[id].subject === subject));
}
for (const tag of practice.tags) {
  const ids = practice.eligible({ subject: tag.subject, problem: String(tag.problemNumber), tag: tag.id });
  assert(ids.every((id) => catalog.questions[id].tags.includes(tag.id)));
  assert(ids.every((id) => Number(practice.byId.get(id).question.groupNumber) === tag.problemNumber));
  const sampled = practice.sample({ tag: tag.id }, 99999);
  assert.equal(sampled.length, ids.length);
  assert.equal(new Set(sampled).size, sampled.length);
}
assert.equal(practice.sample({}, 10).length, 10);
assert.notDeepEqual(Array.from(practice.sample({}, 10, () => 0)), Array.from(practice.sample({}, 10, () => .99)));
for (const count of [0, -1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) assert.throws(() => practice.sample({}, count));
assert.equal(practice.sample({ tag: 'missing' }, 10).length, 0);
const discourse = practice.eligible({ subject: '语法', problem: '7' });
assert(discourse.length);
for (const id of discourse) {
  const question = practice.question(id);
  assert((question.passage || question.question).length > 100, `Missing article: ${id}`);
  assert.equal(question.sourceYear, catalog.questions[id].year);
  assert.equal(question.id, id);
}
const id = practice.pool.find((id) => catalog.questions[id].tags.length > 1);
const tagIds = catalog.questions[id].tags;
const records = [
  { year: catalog.questions[id].year, details: [{ id, results: [true] }] },
  { mode: 'special', details: [{ id, results: [false], answerRevealedBeforeSubmit: true }] },
];
const stats = practice.stats(records);
for (const tid of tagIds) {
  const row = stats.find((row) => row.id === tid);
  assert.equal(row.total, 2); assert.equal(row.correct, 1);
  assert.equal(row.percentage, 50); assert.equal(row.practiced, 1); assert.equal(row.revealed, 1);
}
assert(practice.stats([]).every((row) => row.percentage === null));
// All grammar periods are now eligible, including old five-blank articles.
const grammarIds = Object.values(data.exams).flatMap(exam => exam['语法']).map(q => q.id);
assert.deepEqual(new Set(practice.eligible({ subject: '语法' })), new Set(grammarIds));
assert.equal(grammarIds.length, 609);
assert.equal(practice.pool.length, 1384);
assert.equal(practice.eligible({ subject: '语法', problem: '7' }).length, 144);
const oldest = grammarIds.find(id => practice.byId.get(id).year === '2010.07' && practice.byId.get(id).question.groupNumber === 7);
assert(practice.question(oldest).passage.length > 100);
// Metadata additions remain data-driven: remove one annotation, then restore it.
const reduced = JSON.parse(JSON.stringify(catalog));
delete reduced.questions[oldest];
const partial = SpecialPractice.create(data, reduced);
assert.equal(partial.pool.length, practice.pool.length - 1);
reduced.questions[oldest] = catalog.questions[oldest];
assert(SpecialPractice.create(data, reduced).eligible({ subject: '语法' }).includes(oldest));
const oldStats = practice.stats([{ year: '2010.07', details: [{ id: oldest, results: [true] }] }]);
for (const tid of catalog.questions[oldest].tags) assert.equal(oldStats.find(row => row.id === tid).correct, 1);
console.log(`PASS: ${practice.pool.length} tagged questions, ${practice.tags.length} tags; all grammar periods, cascading filters, unique sampling, count validation, full articles, mixed history statistics`);
