/* Pure practice selection and statistics shared by the UI and regression tests. */
(() => {
  "use strict";
  function create(data, catalog = {}) {
    const byId = new Map();
    for (const [year, exam] of Object.entries(data.exams)) {
      for (const [category, questions] of Object.entries(exam)) {
        questions.forEach((question) => byId.set(question.id, { question, year, category }));
      }
    }
    const tags = catalog.tags || [];
    const tagById = new Map(tags.map((tag) => [tag.id, tag]));
    const annotations = catalog.questions || {};
    const pool = Object.keys(annotations).filter((id) => byId.has(id) && annotations[id].tags.length);
    const subjectOf = (category) => ["文字", "词汇", "文字・词汇"].includes(category) ? "文字・词汇" : category;
    function matches(meta, filter = {}) {
      return (!filter.subject || meta.subject === filter.subject)
        && (!filter.problem || String(meta.problemNumber) === String(filter.problem))
        && (!filter.tag || meta.tags.includes(filter.tag));
    }
    function eligible(filter) { return pool.filter((id) => matches(annotations[id], filter)); }
    function sample(filter, count, random = Math.random) {
      if (!Number.isSafeInteger(count) || count < 1) throw new Error("请输入大于 0 的整数题数。");
      const ids = eligible(filter);
      for (let i = ids.length - 1; i > 0; i--) {
        const j = Math.floor(random() * (i + 1));
        [ids[i], ids[j]] = [ids[j], ids[i]];
      }
      return ids.slice(0, Math.min(count, ids.length));
    }
    function question(id) {
      const entry = byId.get(id);
      if (!entry) return null;
      const meta = annotations[id];
      const source = entry.question;
      return { ...source, sourceYear: entry.year, sourceCategory: entry.category,
        passage: source.passage || (meta?.sharedPassage && meta.sharedPassage !== source.question ? meta.sharedPassage : "") };
    }
    function stats(history) {
      const result = new Map(tags.map((tag) => [tag.id, { ...tag, available: 0, total: 0, correct: 0, seen: new Set(), revealed: 0 }]));
      pool.forEach((id) => annotations[id].tags.forEach((tid) => { if (result.has(tid)) result.get(tid).available++; }));
      for (const record of history) {
        const seenIds = new Set();
        for (const detail of record.details || []) {
          if (seenIds.has(detail.id)) continue;
          seenIds.add(detail.id);
          const meta = annotations[detail.id];
          if (!meta || !Array.isArray(detail.results) || !detail.results.length) continue;
          for (const tid of new Set(meta.tags)) {
            const stat = result.get(tid);
            if (!stat) continue;
            stat.total += detail.results.length;
            stat.correct += detail.results.filter((value) => value === true).length;
            stat.seen.add(detail.id);
            if (detail.answerRevealedBeforeSubmit) stat.revealed += detail.results.length;
          }
        }
      }
      return [...result.values()].map(({ seen, ...stat }) => ({ ...stat, practiced: seen.size,
        percentage: stat.total ? Math.round(stat.correct / stat.total * 100) : null }));
    }
    return { byId, tags, tagById, annotations, pool, subjects: catalog.subjects || [], subjectOf, eligible, sample, question, stats };
  }
  window.SpecialPractice = { create };
})();
