const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
const submit = source.slice(source.indexOf('  function submitExam() {'), source.indexOf('  function leaveExam() {'));
for (const mode of ['period', 'special']) for (const selections of [[1, null, 3], [null, null, null], [1, 2, 2]]) {
  let saved;
  const elements = new Map();
  const state = { submitted: false, questions: [{ id: 'q', expected: [1, 2, 2] }],
    startedAt: Date.now(), results: {}, reasons: {}, optionReasons: {}, orders: {}, checked: {},
    year: '2024.07', category: '语法', practice: mode === 'special' ? {} : null };
  const context = { state, window: { confirm: () => true },
    PRACTICE: { byId: new Map(), annotations: {} }, clearInterval() {},
    pointCount: q => q.expected.length, answeredPointCount: () => selections.filter(Boolean).length,
    expectedAnswers: q => q.expected, selectedAnswers: () => selections,
    isOrderingQuestion: () => false, displayedOptionOrder: () => [1, 2, 3, 4],
    renderQuestionFeedback() {}, renderQuestionNav() {}, saveUiState() {},
    loadHistory: () => [], saveHistory: records => { saved = records[0]; },
    formatDuration: () => '00:01',
    $: selector => {
      if (!elements.has(selector)) elements.set(selector, { scrollIntoView() {} });
      return elements.get(selector);
    },
  };
  vm.runInNewContext(`${submit}\nsubmitExam();`, context);
  const answered = selections.filter(Boolean).length;
  assert.equal(saved.totalPoints, 3);
  assert.equal(saved.total, answered);
  assert.equal(saved.answered, answered);
  assert.equal(saved.percentage, answered === 0 ? null : answered === 2 ? 50 : 100);
  assert.equal(saved.mode, mode);
  assert.equal(saved.details[0].selected.length, 3); // Keep unanswered items available for replay.
  assert.match(elements.get('#score-panel').innerHTML, answered ? /分/ : /未计分/);
}
console.log('PASS: real submission saves answered-only scores in normal and special practice, including empty submissions');
