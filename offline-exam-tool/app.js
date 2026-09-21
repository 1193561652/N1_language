(() => {
  "use strict";

  const DATA = window.EXAM_DATA;
  const PRACTICE = window.SpecialPractice.create(DATA, window.PRACTICE_DATA);
  const HISTORY_KEY = "sbry-n1-offline-history-v1";
  const UI_STATE_KEY = "sbry-n1-offline-ui-state-v1";
  const UI_CATEGORIES = ["文字・词汇", "语法", "阅读", "听力"];
  let projectStorageAvailable = false;
  let projectSyncQueue = Promise.resolve();
  let activeAiQuestionId = null;
  let activeAiRequest = null;
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const state = { year: null, category: null, practice: null, questions: [], answers: {}, reasons: {}, optionReasons: {}, orders: {}, results: {}, checked: {}, aiChats: {}, startedAt: 0, timerId: null, submitted: false, replayMode: false, historyRecordId: null };
  let aiConfigured = false;
  let restoringUiState = false;
  let scrollSaveTimer = null;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[char]);
  const formatExamText = (value) => escapeHtml(value)
    .replaceAll("⟦u⟧", '<u class="exam-underline">')
    .replaceAll("⟦/u⟧", "</u>");
  const formatAnalysisHtml = (value) => escapeHtml(value)
    .replaceAll("【AI 生成解析】", '<span class="ai-analysis-label">AI 生成解析</span>')
    .replaceAll("【AI 点评】", '<span class="ai-comment-label">AI 点评</span>');
  const textBlock = (value, className = "") => value ? `<div class="content-block ${className}">${formatExamText(value)}</div>` : "";
  const formatDuration = (seconds) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const formatDate = (iso) => new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "medium" }).format(new Date(iso));

  function repairOrderingHistory(history) {
    const questionsById = new Map(Object.values(DATA.exams || {}).flatMap((exam) => exam["语法"] || []).map((question) => [question.id, question]));
    let changed = false;
    (history || []).forEach((record) => {
      let recordChanged = false;
      (record.details || []).forEach((detail) => {
        const question = questionsById.get(detail.id);
        const order = (detail.order || []).map(Number);
        if (!question || Number(question.groupNumber) !== 6 || order.length !== 4) return;
        const starPosition = orderingStarIndex(question) + 1;
        const selected = Number(order[starPosition - 1]);
        const expected = Number(question.rightAnswer);
        const result = selected === expected;
        if (Number(detail.starPosition) === starPosition && Number(detail.selected?.[0]) === selected
          && Number(detail.expected?.[0]) === expected && detail.results?.[0] === result) return;
        detail.starPosition = starPosition;
        detail.selected = [selected];
        detail.expected = [expected];
        detail.results = [result];
        changed = true;
        recordChanged = true;
      });
      if (recordChanged) {
        record.correct = (record.details || []).reduce((sum, detail) => sum + (detail.results || []).filter(Boolean).length, 0);
        record.percentage = record.total ? Math.round(record.correct / record.total * 100) : 0;
      }
    });
    return changed;
  }

  function loadHistory() {
    try {
      const value = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
      if (!Array.isArray(value)) return [];
      if (repairOrderingHistory(value)) localStorage.setItem(HISTORY_KEY, JSON.stringify(value));
      return value;
    } catch (_) { return []; }
  }

  function saveHistory(history, { syncProject = true } = {}) {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    renderHistory();
    renderInsights();
    refreshYearOptions();
    if (syncProject && projectStorageAvailable) persistProjectHistory(history);
  }

  function loadUiState() {
    try {
      const value = JSON.parse(sessionStorage.getItem(UI_STATE_KEY) || "null");
      return value && typeof value === "object" ? value : null;
    } catch (_) { return null; }
  }

  function activeViewName() {
    return $(".tab.active")?.dataset.view || "practice";
  }

  function currentQuestionId() {
    const cards = $$("#questions-form .question-card");
    return cards.find((card) => card.getBoundingClientRect().bottom > 140)?.dataset.id || null;
  }

  function saveUiState() {
    if (restoringUiState) return;
    const examActive = Boolean($("#exam-panel") && !$("#exam-panel").hidden && state.questions.length);
    const payload = {
      version: 1,
      view: activeViewName(),
      year: $("#year-select")?.value || state.year,
      category: $("#category-select")?.value || state.category,
      specialFilters: specialFilters(),
      specialCount: $("#special-count").value,
      historyYear: $("#history-year-filter")?.value || "",
      historyCategory: $("#history-category-filter")?.value || "",
      examActive,
      replayMode: Boolean(state.replayMode),
      submitted: Boolean(state.submitted),
      historyRecordId: state.historyRecordId,
      scrollY: Math.max(0, Math.round(window.scrollY || 0)),
      questionId: examActive ? currentQuestionId() : null,
      draft: examActive && !state.replayMode ? {
        practice: state.practice,
        answers: state.answers,
        reasons: state.reasons,
        optionReasons: state.optionReasons,
        orders: state.orders,
        results: state.results,
        checked: state.checked,
        startedAt: state.startedAt,
      } : null,
    };
    try { sessionStorage.setItem(UI_STATE_KEY, JSON.stringify(payload)); } catch (_) { /* storage unavailable */ }
  }

  function restoreScrollPosition(saved) {
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
      const target = saved.questionId && document.getElementById(`question-${saved.questionId}`);
      if (target && !Number.isFinite(Number(saved.scrollY))) target.scrollIntoView({ block: "start" });
      else window.scrollTo({ top: Math.max(0, Number(saved.scrollY) || 0), behavior: "auto" });
      restoringUiState = false;
      saveUiState();
    }));
  }

  function setStorageStatus(message, stateName = "") {
    const status = $("#storage-status");
    if (!status) return;
    status.textContent = message;
    status.dataset.state = stateName;
  }

  function mergeHistory(primary, secondary) {
    const records = [...secondary, ...primary].filter((item) => item?.id);
    const byId = new Map(records.map((item) => [item.id, item]));
    const merged = [...byId.values()].sort((a, b) => String(b.submittedAt).localeCompare(String(a.submittedAt)));
    repairOrderingHistory(merged);
    return merged;
  }

  function persistProjectHistory(history) {
    projectSyncQueue = projectSyncQueue.catch(() => undefined).then(async () => {
      setStorageStatus("正在写入项目答题记录……", "syncing");
      const response = await fetch("/api/history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: 2, history })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setStorageStatus("答题记录已保存到项目", "project");
    }).catch((error) => {
      setStorageStatus(`项目记录写入失败（浏览器缓存仍保留）：${error.message}`, "error");
    });
    return projectSyncQueue;
  }

  async function initializeProjectStorage() {
    if (location.protocol === "file:") {
      setStorageStatus("当前为直接打开模式：记录仅保存在浏览器；使用启动脚本可写入项目", "browser");
      return;
    }
    try {
      const response = await fetch("/api/history", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      if (!payload || !Array.isArray(payload.history)) throw new Error("项目历史格式不正确");
      projectStorageAvailable = true;
      const merged = mergeHistory(loadHistory(), payload.history);
      saveHistory(merged);
      setStorageStatus("答题记录已连接项目存储", "project");
    } catch (_) {
      setStorageStatus("未连接项目存储：记录仅保存在浏览器", "browser");
    }
  }

  function switchView(name) {
    if (name !== "practice") closeAiDrawer();
    $$(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.view === name));
    $$(".view").forEach((view) => {
      const active = view.id === `${name}-view`;
      view.hidden = !active;
      view.classList.toggle("active", active);
    });
    if (name === "history") renderHistory();
    if (name === "ai-config") refreshAiConfigStatus();
    saveUiState();
  }

  function setAiConfigStatus(message, stateName = "") {
    const status = $("#gemini-config-status");
    if (!status) return;
    status.textContent = message;
    status.dataset.state = stateName;
  }

  async function refreshAiConfigStatus() {
    if (location.protocol === "file:") {
      aiConfigured = false;
      setAiConfigStatus("直接打开 HTML 时不可用，请通过项目启动器访问。", "error");
      return;
    }
    setAiConfigStatus("正在检查配置……", "syncing");
    try {
      const response = await fetch("/api/ai/config", { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      aiConfigured = Boolean(payload.configured);
      setAiConfigStatus(aiConfigured ? `已配置 · ${payload.model}` : "尚未配置 API Key", aiConfigured ? "configured" : "");
    } catch (error) {
      aiConfigured = false;
      setAiConfigStatus(`无法连接本地配置服务：${error.message}`, "error");
    }
  }

  async function saveGeminiConfig() {
    const input = $("#gemini-api-key");
    const key = input.value.trim();
    if (!key) {
      setAiConfigStatus("请输入 API Key。", "error");
      input.focus();
      return;
    }
    if (location.protocol === "file:") {
      setAiConfigStatus("请先用项目启动器打开题库，再保存 API Key。", "error");
      return;
    }
    const button = $("#save-gemini-key");
    button.disabled = true;
    setAiConfigStatus("正在保存到项目本地……", "syncing");
    try {
      const response = await fetch("/api/ai/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apiKey: key }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      input.value = "";
      aiConfigured = true;
      setAiConfigStatus(`已保存到项目本地 · ${payload.model}`, "configured");
    } catch (error) {
      aiConfigured = false;
      setAiConfigStatus(`保存失败：${error.message}`, "error");
    } finally {
      button.disabled = false;
    }
  }

  function specialFilters() {
    return { subject: $("#special-subject").value, problem: $("#special-problem").value, tag: $("#special-tag").value };
  }

  function optionsFor(select, entries, selected = select.value) {
    select.innerHTML = '<option value="">－（全部）</option>' + entries.map(([value, label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`).join("");
    select.value = entries.some(([value]) => String(value) === String(selected)) ? selected : "";
  }

  function updateSpecialProblems() {
    const subject = $("#special-subject").value;
    const groups = new Map();
    PRACTICE.tags.filter((tag) => !subject || tag.subject === subject).forEach((tag) => {
      groups.set(String(tag.problemNumber), `問題${tag.problemNumber} · ${tag.problemName}`);
    });
    optionsFor($("#special-problem"), [...groups.entries()]);
  }

  function updateSpecialTags() {
    const { subject, problem } = specialFilters();
    const tags = PRACTICE.tags.filter((tag) => (!subject || tag.subject === subject) && (!problem || String(tag.problemNumber) === problem));
    optionsFor($("#special-tag"), tags.map((tag) => [tag.id, `${problem ? "" : `問題${tag.problemNumber} · `}${tag.name}`]));
    updateSpecialSummary();
  }

  function updateSpecialSummary() {
    const count = Number($("#special-count").value);
    const available = PRACTICE.eligible(specialFilters()).length;
    const valid = Number.isSafeInteger(count) && count > 0;
    $("#special-start").disabled = !available || !valid;
    $("#special-summary").textContent = !available ? "当前范围暂无已标记题目，请选择其他范围。"
      : !valid ? `可选 ${available} 道题。请输入大于 0 的整数题数。`
      : `可选 ${available} 道题，本次随机抽取 ${Math.min(count, available)} 道${count > available ? "（不足指定题数，将使用全部可选题目）" : ""}。`;
    $("#special-error").textContent = "";
  }

  function restoreSpecialFilters(filters) {
    $("#special-subject").value = PRACTICE.subjects.includes(filters.subject) ? filters.subject : "";
    updateSpecialProblems();
    $("#special-problem").value = filters.problem || "";
    updateSpecialTags();
    $("#special-tag").value = filters.tag || "";
    updateSpecialSummary();
  }

  function practiceTitle(practice) {
    const filters = practice?.filters || {};
    const tag = PRACTICE.tagById.get(filters.tag);
    const group = PRACTICE.tags.find((item) => String(item.problemNumber) === String(filters.problem));
    return ["专项练习", filters.subject || "文字・词汇＋语法", tag ? `問題${tag.problemNumber} · ${tag.name}` : group ? `問題${group.problemNumber} · ${group.problemName}` : "全部考点"].join(" · ");
  }

  function startSpecialExam() {
    if (state.questions.length && !state.submitted && !window.confirm("当前有未提交的答题，确定重新生成专项练习吗？")) return;
    try {
      const filters = specialFilters();
      const requestedCount = Number($("#special-count").value);
      const questionIds = PRACTICE.sample(filters, requestedCount);
      if (!questionIds.length) throw new Error("当前范围暂无已标记题目。");
      startExam(null, { filters, requestedCount, questionIds });
      switchView("practice");
    } catch (error) {
      $("#special-error").textContent = error.message;
    }
  }

  function initSpecialSelectors() {
    optionsFor($("#special-subject"), PRACTICE.subjects.map((subject) => [subject, subject]));
    updateSpecialProblems();
    updateSpecialTags();
    $("#special-subject").addEventListener("change", () => {
      $("#special-problem").value = "";
      $("#special-tag").value = "";
      updateSpecialProblems(); updateSpecialTags(); saveUiState();
    });
    $("#special-problem").addEventListener("change", () => {
      $("#special-tag").value = "";
      updateSpecialTags(); saveUiState();
    });
    $("#special-tag").addEventListener("change", () => { updateSpecialSummary(); saveUiState(); });
    $("#special-count").addEventListener("input", () => { updateSpecialSummary(); saveUiState(); });
    $("#special-start").addEventListener("click", startSpecialExam);
    $$('[data-go-special]').forEach((button) => button.addEventListener("click", () => switchView("special")));
    $("#tag-insights").addEventListener("click", (event) => {
      const button = event.target.closest("[data-practice-tag]");
      if (!button) return;
      const tag = PRACTICE.tagById.get(button.dataset.practiceTag);
      if (!tag) return;
      restoreSpecialFilters({ subject: tag.subject, problem: String(tag.problemNumber), tag: tag.id });
      switchView("special");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  function renderTagInsights() {
    const stats = PRACTICE.stats(loadHistory());
    const target = $("#tag-insights");
    const openSubjects = new Set([...target.querySelectorAll('details[open]')].map((node) => node.dataset.subject));
    target.innerHTML = `<div class="insights-heading"><div><p class="section-kicker">专项能力</p><h2>各考点正确率</h2></div></div>
      <p class="muted">统计普通答题与专项练习的全部已提交记录；重复练习按次计入，未作答计错。多标签题分别计入各考点，不能相加作为总题数。暂无记录显示“—”。</p>
      ${PRACTICE.subjects.map((subject) => {
        const rows = stats.filter((stat) => stat.subject === subject).sort((a, b) => (a.percentage ?? 101) - (b.percentage ?? 101) || a.problemNumber - b.problemNumber);
        return `<details class="insight-card tag-subject" data-subject="${escapeHtml(subject)}" ${openSubjects.has(subject) ? "open" : ""}>
          <summary><strong>${escapeHtml(subject)}</strong><span>${rows.filter((row) => row.total).length} / ${rows.length} 个考点已有记录 · 展开查看</span></summary>
          <div class="tag-table-wrap"><table class="tag-table"><thead><tr><th>问题 / 考点</th><th>正确率</th><th>正确 / 作答</th><th>做过 / 题池</th><th>提前看答案</th><th>练习</th></tr></thead><tbody>
          ${rows.map((row) => `<tr><td><small>問題${row.problemNumber} · ${escapeHtml(row.problemName)}</small><strong>${escapeHtml(row.name)}</strong></td>
            <td class="${row.percentage !== null && row.percentage < 60 ? "low-score" : ""}">${row.percentage === null ? "—" : `${row.percentage}%`}</td>
            <td>${row.correct} / ${row.total}</td><td>${row.practiced} / ${row.available}</td><td>${row.revealed}</td>
            <td><button class="text-button" data-practice-tag="${escapeHtml(row.id)}" ${row.available ? "" : "disabled"}>练习 →</button></td></tr>`).join("")}
          </tbody></table></div></details>`;
      }).join("")}`;
  }

  function initSelectors() {
    $("#category-select").innerHTML = UI_CATEGORIES.map((name) => `<option value="${name}">${name}</option>`).join("");
    refreshYearOptions();
    updateSelectionSummary();
  }

  function refreshYearOptions() {
    const select = $("#year-select");
    if (!select) return;
    const selected = select.value || DATA.years[0];
    const selectedCategory = $("#category-select")?.value || UI_CATEGORIES[0];
    const exactByYear = new Map();
    const legacyByYear = new Map();
    loadHistory().forEach((record) => {
      if (!record?.year || record.mode === "special") return;
      const isExact = record.category === selectedCategory;
      const isLegacyMerged = selectedCategory === "文字・词汇" && ["文字", "词汇"].includes(record.category);
      if (!isExact && !isLegacyMerged) return;
      const target = isExact ? exactByYear : legacyByYear;
      const previous = target.get(record.year);
      if (!previous || String(record.submittedAt) > String(previous.submittedAt)) target.set(record.year, record);
    });
    select.innerHTML = DATA.years.map((year) => {
      const record = exactByYear.get(year) || legacyByYear.get(year);
      const calculated = record?.total ? Math.round(Number(record.correct || 0) / Number(record.total) * 100) : null;
      const accuracy = Number.isFinite(Number(record?.percentage)) ? Number(record.percentage) : calculated;
      const suffix = Number.isFinite(accuracy) ? `（${selectedCategory}上次正确率 ${accuracy}%）` : "";
      return `<option value="${escapeHtml(year)}">${escapeHtml(year)}${suffix}</option>`;
    }).join("");
    if (DATA.years.includes(selected)) select.value = selected;
  }

  function selectedQuestions() {
    const exam = DATA.exams[$("#year-select").value];
    const category = $("#category-select").value;
    if (category === "文字・词汇") return [...(exam["文字"] || []), ...(exam["词汇"] || [])];
    return exam[category] || [];
  }

  function pointCount(question) {
    return question.qaType === 4 && Number(question.rightAnswer) > 9 ? 2 : 1;
  }

  function isOrderingQuestion(question) {
    return (PRACTICE.byId.get(question.id)?.category || state.category) === "语法" && Number(question.groupNumber) === 6 && (question.options || []).length === 4;
  }

  function orderingStarIndex(question) {
    const explicitPosition = Number(question.starPosition);
    if (explicitPosition >= 1 && explicitPosition <= 4) return explicitPosition - 1;
    let text = String(question.question || "");
    if (text.includes("---")) text = text.split("---").at(-1);
    if (!text.includes("★")) return 2;
    if (text.includes("--+")) return Math.max(0, Math.min(3, (text.slice(0, text.indexOf("★")).match(/--/g) || []).length));
    text = text.replaceAll("\\_", "_").replaceAll("⟦u⟧", "").replaceAll("⟦/u⟧", "");
    const line = text.split(/\r?\n/).find((value) => value.includes("★")) || text;
    const slots = [...line.matchAll(/(?:[_＿]+)?★(?:[_＿]+)?|[_＿]+/g)];
    const starSlot = slots.findIndex((slot) => slot[0].includes("★"));
    return starSlot >= 0 ? Math.max(0, Math.min(3, starSlot)) : 2;
  }

  function updateSelectionSummary() {
    const questions = selectedQuestions();
    const audio = questions.filter((q) => q.audio).length;
    const images = questions.reduce((sum, q) => sum + q.images.length, 0);
    $("#question-count").textContent = questions.reduce((sum, q) => sum + pointCount(q), 0);
    $("#media-summary").textContent = audio || images ? `${audio} 段听力 · ${images} 张图片` : "纯文字试题";
  }

  function optionMarkup(question, subIndex = null) {
    const count = Number(question.optionCount) || 4;
    const options = question.options.length ? question.options : Array.from({ length: count }, (_, i) => `选项 ${i + 1}`);
    const name = subIndex === null ? `answer-${question.id}` : `answer-${question.id}-${subIndex}`;
    const scope = subIndex === null ? "main" : String(subIndex);
    return `<div class="option-list">${options.map((label, index) => `
      <div class="option-with-reason">
        <label class="option" data-option="${index + 1}">
          <input type="radio" name="${name}" value="${index + 1}" data-question="${question.id}" ${subIndex === null ? "" : `data-sub="${subIndex}"`}>
          <span><strong>${index + 1}.</strong> ${formatExamText(label)}</span>
        </label>
        <textarea class="option-reason" data-option-reason-question="${question.id}" data-option-reason-key="${scope}:${index + 1}" maxlength="1200" placeholder="为什么选择或排除此项（可选）"></textarea>
      </div>`).join("")}</div>`;
  }

  function orderingMarkup(question) {
    const starPosition = orderingStarIndex(question) + 1;
    return `<div class="ordering-control" data-order-question="${escapeHtml(question.id)}">
      <div class="ordering-instruction"><strong>句子排序</strong><span>依次点击选项加入排序；第 ${starPosition} 位是 ★，将自动作为本题答案。</span></div>
      <div class="order-replay-note" hidden></div>
      <div class="order-slots" aria-label="当前排列"></div>
      <div class="ordering-options">${question.options.map((label, index) => `
        <div class="ordering-option-row">
          <button type="button" class="order-choice" data-order-add="${index + 1}"><span class="order-choice-number">${index + 1}</span><span>${formatExamText(label)}</span><small></small></button>
          <textarea class="option-reason" data-option-reason-question="${question.id}" data-option-reason-key="main:${index + 1}" maxlength="1200" placeholder="为什么把此项放在这个位置（可选）"></textarea>
        </div>`).join("")}</div>
      <button type="button" class="order-reset" data-order-reset>清空排序</button>
    </div>`;
  }

  function questionMarkup(question, index, seenPassages) {
    const passageKey = `${question.groupNumber}|${question.passage}`;
    const showPassage = question.passage && (state.practice || !seenPassages.has(passageKey));
    if (showPassage) seenPassages.add(passageKey);
    const combined = question.qaType === 4 && Number(question.rightAnswer) > 9;
    const origin = PRACTICE.byId.get(question.id);
    const periodLabel = state.practice && origin ? `${escapeHtml(origin.year)} · ${escapeHtml(PRACTICE.subjectOf(origin.category))} · ` : "";
    const sourceLabel = question.source ? ` · ${escapeHtml(question.source)}` : "";
    return `<article class="question-card" id="question-${question.id}" data-id="${question.id}">
      <div class="question-main">
      <div class="question-meta">
        <span class="question-number">第 ${index + 1} 题${combined ? "（含两问）" : ""}</span>
        <span class="question-id-wrap" title="${escapeHtml(question.id)}"><code>${escapeHtml(question.id)}</code><button type="button" class="copy-id-button" data-copy-question-id="${escapeHtml(question.id)}" aria-label="复制题目 ID" title="复制题目 ID"><span aria-hidden="true">⧉</span></button></span>
        ${state.replayMode ? `<button type="button" class="question-ai-open" data-ai-open="${escapeHtml(question.id)}">AI 解析</button>` : ""}
        <span class="question-source">${periodLabel}大题 ${escapeHtml(question.groupNumber)}${sourceLabel}</span>
      </div>
      ${textBlock(question.groupTitle, "group-title")}
      ${showPassage ? textBlock(question.passage, "passage") : ""}
      ${textBlock(question.title)}${textBlock(question.question)}${textBlock(question.subQuestion)}
      ${question.images.map((path) => `<img class="question-image" src="${encodeURI(path)}" alt="题目图片" loading="lazy">`).join("")}
      ${question.audio ? `<audio controls preload="metadata" src="${encodeURI(question.audio)}">浏览器不支持音频播放。</audio>` : ""}
      ${isOrderingQuestion(question) ? orderingMarkup(question) : combined ? `
        <fieldset class="sub-answer"><legend>问题一</legend>${optionMarkup(question, 0)}</fieldset>
        <fieldset class="sub-answer"><legend>问题二</legend>${optionMarkup(question, 1)}</fieldset>` : optionMarkup(question)}
      <label class="reason-field">答题理由（可选，供后续 AI 分析）
        <textarea data-reason-question="${question.id}" maxlength="2000" placeholder="例如：为什么选择这个答案、排除了哪些选项、哪里不确定……"></textarea>
      </label>
      <div class="question-check-actions"><button type="button" class="check-answer-button" data-check-question="${escapeHtml(question.id)}">显示正确答案</button><span>只检查本题，不提交、不保存记录</span></div>
      <div class="explanation" hidden></div>
      </div>
    </article>`;
  }

  function startExam(savedDraft = null, practice = savedDraft?.practice || null) {
    closeAiDrawer();
    state.practice = practice;
    state.year = practice ? "专项练习" : $("#year-select").value;
    state.category = practice ? (practice.filters.subject || "文字・词汇＋语法") : $("#category-select").value;
    state.questions = practice ? practice.questionIds.map((id) => PRACTICE.question(id)).filter(Boolean) : selectedQuestions();
    if (!state.questions.length) {
      window.alert("当前题库中没有可用题目，请重新生成。");
      state.practice = null;
      return;
    }
    state.answers = { ...(savedDraft?.answers || {}) };
    state.reasons = { ...(savedDraft?.reasons || {}) };
    state.optionReasons = Object.fromEntries(Object.entries(savedDraft?.optionReasons || {}).map(([id, values]) => [id, { ...(values || {}) }]));
    state.orders = Object.fromEntries(Object.entries(savedDraft?.orders || {}).map(([id, values]) => [id, [...(values || [])]]));
    state.results = { ...(savedDraft?.results || {}) };
    state.checked = { ...(savedDraft?.checked || {}) };
    state.aiChats = {};
    state.replayMode = false;
    state.historyRecordId = null;
    state.startedAt = Number(savedDraft?.startedAt) || Date.now();
    state.submitted = false;
    $("#exam-title").textContent = state.practice ? practiceTitle(state.practice) : `${state.year} · ${state.category}`;
    $("#back-button").textContent = state.practice ? "← 返回专项练习" : "← 返回选择";
    const seenPassages = new Set();
    $("#questions-form").innerHTML = state.questions.map((question, index) => questionMarkup(question, index, seenPassages)).join("");
    state.questions.forEach((question) => {
      if (isOrderingQuestion(question)) renderOrderingControl(question.id);
      const card = $(`#question-${CSS.escape(question.id)}`);
      const savedAnswer = state.answers[question.id];
      card?.querySelectorAll("input[data-question]").forEach((input) => {
        const selected = input.dataset.sub === undefined ? savedAnswer : (Array.isArray(savedAnswer) ? savedAnswer[Number(input.dataset.sub)] : null);
        input.checked = Number(input.value) === Number(selected);
      });
      const reasonInput = card?.querySelector("textarea[data-reason-question]");
      if (reasonInput) reasonInput.value = state.reasons[question.id] || "";
      card?.querySelectorAll("textarea[data-option-reason-key]").forEach((textarea) => {
        textarea.value = state.optionReasons[question.id]?.[textarea.dataset.optionReasonKey] || "";
      });
      if (state.checked[question.id]) showQuestionAnswer(question.id);
    });
    $("#setup-panel").hidden = true;
    $("#exam-panel").hidden = false;
    $("#score-panel").hidden = true;
    $("#submit-button").hidden = false;
    $("#submit-bottom-button").hidden = false;
    clearInterval(state.timerId);
    state.timerId = setInterval(updateTimer, 1000);
    updateTimer();
    updateProgress();
    renderQuestionNav();
    window.scrollTo({ top: 0, behavior: savedDraft ? "auto" : "smooth" });
    saveUiState();
  }

  function updateTimer() {
    $("#timer").textContent = formatDuration(Math.floor((Date.now() - state.startedAt) / 1000));
  }

  function answeredPointCount() {
    return state.questions.reduce((sum, q) => {
      const answer = state.answers[q.id];
      return sum + (Array.isArray(answer) ? answer.filter(Boolean).length : answer ? 1 : 0);
    }, 0);
  }

  function updateProgress() {
    const total = state.questions.reduce((sum, q) => sum + pointCount(q), 0);
    $("#answer-progress").textContent = `已答 ${answeredPointCount()} / ${total}`;
  }

  function questionHasSelection(question) {
    if ((state.orders[question.id] || []).length) return true;
    const answer = state.answers[question.id];
    return Array.isArray(answer) ? answer.some(Boolean) : Boolean(answer);
  }

  function renderQuestionNav() {
    const nav = $("#question-nav");
    if (!nav) return;
    nav.innerHTML = `<div class="question-nav-heading"><strong>题目目录</strong><span>${state.questions.length} 题</span></div>
      <div class="question-nav-legend">
        <span><i class="nav-dot unanswered"></i>未选择</span><span><i class="nav-dot selected"></i>已选择</span>
        <span><i class="nav-dot correct"></i>正确</span><span><i class="nav-dot wrong"></i>错误</span>
      </div>
      <div class="question-nav-grid">${state.questions.map((question, index) => {
        const results = state.results[question.id];
        const status = (state.submitted || state.checked[question.id]) && results
          ? (results.every(Boolean) ? "correct" : "wrong")
          : (questionHasSelection(question) ? "selected" : "unanswered");
        return `<button type="button" class="question-nav-button ${status}" data-nav-question="${escapeHtml(question.id)}" title="第 ${index + 1} 题 · ${escapeHtml(question.id)}">${index + 1}</button>`;
      }).join("")}</div>`;
  }

  function renderOrderingControl(questionId) {
    const question = state.questions.find((item) => item.id === questionId);
    const control = [...document.querySelectorAll(".ordering-control")]
      .find((element) => element.dataset.orderQuestion === questionId);
    if (!question || !control) return;
    const order = state.orders[questionId] || [];
    const starIndex = orderingStarIndex(question);
    const replayNote = control.querySelector(".order-replay-note");
    if (replayNote) {
      replayNote.hidden = !(state.replayMode && order.length === 0);
      replayNote.textContent = `这条旧历史创建时尚未保存完整排序，仅保留了 ★ 位置答案：${state.answers[questionId] || "未作答"}。`;
    }
    const slots = control.querySelector(".order-slots");
    slots.innerHTML = Array.from({ length: 4 }, (_, position) => {
      const optionNumber = order[position];
      const star = position === starIndex;
      const label = optionNumber ? question.options[optionNumber - 1] : "等待选择";
      return `<div class="order-slot ${optionNumber ? "filled" : ""} ${star ? "star-slot" : ""}">
        <span class="order-position">${star ? "★" : position + 1}</span>
        <span class="order-fragment">${optionNumber ? `<b>${optionNumber}.</b> ${formatExamText(label)}` : label}</span>
        ${optionNumber && !state.submitted ? `<span class="order-actions"><button type="button" data-order-move="-1" data-order-index="${position}" aria-label="向左移动" ${position === 0 ? "disabled" : ""}>←</button><button type="button" data-order-move="1" data-order-index="${position}" aria-label="向右移动" ${position === order.length - 1 ? "disabled" : ""}>→</button><button type="button" data-order-remove="${position}" aria-label="移除此项">×</button></span>` : ""}
      </div>`;
    }).join("");
    control.querySelectorAll("button[data-order-add]").forEach((button) => {
      const optionNumber = Number(button.dataset.orderAdd);
      const position = order.indexOf(optionNumber);
      button.disabled = state.submitted || position >= 0;
      button.classList.toggle("used", position >= 0);
      const badge = button.querySelector("small");
      if (badge) badge.textContent = position >= 0 ? `第 ${position + 1} 位${position === starIndex ? " · ★" : ""}` : "加入排序";
    });
    const reset = control.querySelector("[data-order-reset]");
    if (reset) reset.disabled = state.submitted || order.length === 0;
  }

  function syncOrderingAnswer(questionId) {
    const question = state.questions.find((item) => item.id === questionId);
    const order = state.orders[questionId] || [];
    if (question && order.length === 4) state.answers[questionId] = order[orderingStarIndex(question)];
    else delete state.answers[questionId];
    renderOrderingControl(questionId);
    updateProgress();
    if (state.checked[questionId]) showQuestionAnswer(questionId);
    else renderQuestionNav();
  }

  function expectedAnswers(question) {
    const raw = String(question.rightAnswer);
    return question.qaType === 4 && Number(question.rightAnswer) > 9
      ? raw.split("").map(Number)
      : [Number(question.rightAnswer)];
  }

  function selectedAnswers(question) {
    const selectedRaw = state.answers[question.id];
    return Array.isArray(selectedRaw) ? selectedRaw : [selectedRaw || null];
  }

  function answerLabels(question, answers) {
    return (answers || []).map((answer) => {
      const number = Number(answer);
      return answer == null ? null : { number, text: question.options?.[number - 1] || "" };
    });
  }

  function readingArticleContext(question) {
    if (question.passage) return question.passage;
    if (state.category !== "阅读") return "";
    const ownText = String(question.question || "");
    if (ownText.length >= 140) return ownText;
    const currentIndex = state.questions.indexOf(question);
    for (let index = currentIndex - 1; index >= 0; index -= 1) {
      const candidate = state.questions[index];
      if (String(candidate.groupNumber) !== String(question.groupNumber)) break;
      if (candidate.passage) return candidate.passage;
      const candidateText = String(candidate.question || "");
      if (candidateText.length >= 140) return candidateText;
    }
    return "";
  }

  function buildAiQuestionContext(question) {
    const selected = selectedAnswers(question);
    const expected = expectedAnswers(question);
    const order = [...(state.orders[question.id] || [])];
    return {
      examLevel: "JLPT N1",
      period: PRACTICE.byId.get(question.id)?.year || state.year,
      subject: PRACTICE.subjectOf(PRACTICE.byId.get(question.id)?.category || state.category),
      displayedQuestionNumber: state.questions.indexOf(question) + 1,
      sourceQuestionNumber: question.number ?? null,
      questionId: question.id,
      majorQuestionNumber: question.groupNumber ?? null,
      majorQuestionInstruction: question.groupTitle || "",
      articleOrPassageFullText: readingArticleContext(question),
      title: question.title || "",
      questionText: question.question || "",
      subQuestionText: question.subQuestion || "",
      options: (question.options || []).map((text, index) => ({ number: index + 1, text })),
      userAnswer: answerLabels(question, selected),
      correctAnswer: answerLabels(question, expected),
      userOrdering: order.map((number, index) => ({ position: index + 1, optionNumber: number, text: question.options?.[number - 1] || "" })),
      userQuestionReason: state.reasons[question.id] || "",
      userOptionReasons: state.optionReasons[question.id] || {},
    };
  }

  function renderAiChat(questionId) {
    const panel = $(`[data-ai-question="${CSS.escape(questionId)}"]`);
    if (!panel) return;
    const messages = state.aiChats[questionId] || [];
    const container = panel.querySelector(".ai-chat-messages");
    container.innerHTML = messages.length ? messages.map((message) => `
      <div class="ai-chat-message ${message.role === "model" ? "model" : "user"}">
        <strong>${message.role === "model" ? "AI" : "我"}</strong>
        <div>${escapeHtml(message.text).replaceAll("\n", "<br>")}</div>
      </div>`).join("") : '<p class="ai-chat-empty">询问这道题的考点、错误原因或近义表达。题目文章、你的答案和正确答案会自动加入上下文。</p>';
    container.scrollTop = container.scrollHeight;
  }

  function positionAiDrawer({ resetSize = false } = {}) {
    const drawer = $("#question-ai-drawer");
    const card = activeAiQuestionId && document.getElementById(`question-${activeAiQuestionId}`);
    if (!drawer || drawer.hidden || !card) return;
    const rect = card.getBoundingClientRect();
    const margin = 12;
    const viewportWidth = document.documentElement.clientWidth;
    const availableRight = Math.floor(viewportWidth - rect.right - margin * 2);
    const attachRight = viewportWidth > 980 && availableRight >= 280;
    const constrainedHeight = Math.max(224, Math.floor(rect.height));
    const constrainedWidth = attachRight ? availableRight : Math.floor(rect.width);
    drawer.classList.toggle("attached-right", attachRight);
    drawer.classList.toggle("attached-below", !attachRight);
    drawer.style.setProperty("--ai-drawer-max-height", `${constrainedHeight}px`);
    drawer.style.setProperty("--ai-drawer-max-width", attachRight ? `${constrainedWidth}px` : "100%");
    if (resetSize) {
      // A pixel width copied from the card creates a feedback loop when the drawer
      // is placed inside that same card: every layout pass can add the card padding
      // again and widen the whole document. Let CSS resolve 100% in below mode.
      drawer.style.width = attachRight ? `${constrainedWidth}px` : "100%";
      drawer.style.height = `${Math.round(Math.min(544, constrainedHeight))}px`;
    }
  }

  function openAiDrawer(questionId) {
    const question = state.questions.find((item) => item.id === questionId);
    const drawer = $("#question-ai-drawer");
    const card = document.getElementById(`question-${questionId}`);
    if (!question || !drawer || !card || !state.replayMode) return;
    if (activeAiRequest && activeAiRequest.questionId !== questionId) stopAiGeneration("已停止上一题的生成");
    drawer.closest(".question-card")?.classList.remove("ai-drawer-host");
    activeAiQuestionId = questionId;
    card.classList.add("ai-drawer-host");
    card.appendChild(drawer);
    drawer.dataset.aiQuestion = questionId;
    $("#ai-drawer-title").textContent = `第 ${state.questions.indexOf(question) + 1} 题 · AI 解析`;
    $("#ai-drawer-question-id").textContent = `${question.id} · Gemini 3.6 Flash`;
    $("#ai-drawer-input").dataset.aiInput = questionId;
    $("#ai-drawer-send").dataset.aiSend = questionId;
    drawer.hidden = false;
    renderAiChat(questionId);
    setAiChatStatus(questionId, "");
    positionAiDrawer({ resetSize: true });
    $("#ai-drawer-input").focus();
  }

  function closeAiDrawer() {
    if (activeAiRequest) stopAiGeneration("已停止生成");
    const drawer = $("#question-ai-drawer");
    if (drawer) {
      drawer.closest(".question-card")?.classList.remove("ai-drawer-host");
      drawer.hidden = true;
      delete drawer.dataset.aiQuestion;
      document.body.appendChild(drawer);
    }
    activeAiQuestionId = null;
  }

  function setAiChatStatus(questionId, message, stateName = "") {
    const status = $(`[data-ai-question="${CSS.escape(questionId)}"] .ai-chat-status`);
    if (!status) return;
    status.textContent = message;
    status.dataset.state = stateName;
  }

  function setAiGenerating(generating) {
    const button = $("#ai-drawer-send");
    const input = $("#ai-drawer-input");
    if (!button || !input) return;
    button.classList.toggle("generating", generating);
    button.textContent = generating ? "" : "发送";
    button.setAttribute("aria-label", generating ? "停止生成" : "发送");
    button.title = generating ? "停止本次输出" : "发送";
    input.disabled = generating;
  }

  function stopAiGeneration(message = "已停止生成") {
    const request = activeAiRequest;
    if (!request) return;
    activeAiRequest = null;
    request.controller.abort();
    if (!request.assistantMessage.text) {
      const messages = state.aiChats[request.questionId] || [];
      const index = messages.indexOf(request.assistantMessage);
      if (index >= 0) messages.splice(index, 1);
    }
    renderAiChat(request.questionId);
    setAiChatStatus(request.questionId, message, "");
    setAiGenerating(false);
  }

  async function sendAiQuestion(questionId) {
    if (activeAiRequest) {
      stopAiGeneration("已停止生成，已保留当前回答");
      return;
    }
    const question = state.questions.find((item) => item.id === questionId);
    const panel = $(`[data-ai-question="${CSS.escape(questionId)}"]`);
    const input = panel?.querySelector("textarea[data-ai-input]");
    const button = panel?.querySelector("button[data-ai-send]");
    const text = input?.value.trim();
    if (!question || !input || !button || !text) return;
    if (!aiConfigured) await refreshAiConfigStatus();
    if (!aiConfigured) {
      setAiChatStatus(questionId, "请先在顶部“AI 配置”中保存 API Key。", "error");
      return;
    }

    state.aiChats[questionId] ||= [];
    state.aiChats[questionId].push({ role: "user", text });
    const assistantMessage = { role: "model", text: "" };
    state.aiChats[questionId].push(assistantMessage);
    input.value = "";
    renderAiChat(questionId);
    const controller = new AbortController();
    const requestState = { questionId, controller, assistantMessage };
    activeAiRequest = requestState;
    setAiGenerating(true);
    setAiChatStatus(questionId, "Gemini 正在流式回答……", "syncing");
    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ context: buildAiQuestionContext(question), messages: state.aiChats[questionId] }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let completed = false;
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split("\n");
        buffer = done ? "" : lines.pop();
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (event.type === "delta") {
            assistantMessage.text += String(event.text || "");
            renderAiChat(questionId);
          } else if (event.type === "continuation") {
            setAiChatStatus(questionId, `已到达输出上限，正在自动续写第 ${event.count} 次……`, "syncing");
          } else if (event.type === "done") {
            completed = true;
            const suffix = Number(event.continuations) > 0 ? ` · 自动续写 ${event.continuations} 次` : "";
            setAiChatStatus(questionId, `由 Gemini 3.6 Flash 回答完成${suffix}`, "configured");
          } else if (event.type === "error") {
            throw new Error(event.error || "流式回答失败");
          }
        }
        if (done) break;
      }
      if (!completed) throw new Error("连接提前结束");
    } catch (error) {
      if (error.name !== "AbortError") setAiChatStatus(questionId, `请求失败：${error.message}`, "error");
    } finally {
      if (activeAiRequest === requestState) {
        activeAiRequest = null;
        setAiGenerating(false);
        input.focus();
      }
    }
  }

  function renderQuestionFeedback(question, selected, expected, results) {
    const card = $(`#question-${CSS.escape(question.id)}`);
    if (!card) return;
    const correct = results.every(Boolean);
    const unanswered = selected.every((value) => !value);
    card.classList.remove("correct", "wrong");
    card.classList.add(correct ? "correct" : "wrong");

    if (isOrderingQuestion(question)) {
      renderOrderingControl(question.id);
      card.querySelectorAll("button[data-order-add]").forEach((button) => {
        button.classList.remove("answer-right", "answer-wrong");
        const optionNumber = Number(button.dataset.orderAdd);
        if (optionNumber === expected[0]) button.classList.add("answer-right");
        if (optionNumber === selected[0] && optionNumber !== expected[0]) button.classList.add("answer-wrong");
      });
    } else {
      expected.forEach((answer, subIndex) => {
        const suffix = expected.length === 1 ? "" : `-${subIndex}`;
        card.querySelectorAll(`input[name="answer-${CSS.escape(question.id)}${suffix}"]`).forEach((input) => {
          const label = input.closest(".option");
          label.classList.remove("answer-right", "answer-wrong");
          if (Number(input.value) === answer) label.classList.add("answer-right");
          if (input.checked && Number(input.value) !== answer) label.classList.add("answer-wrong");
          input.disabled = state.submitted;
        });
      });
    }

    const order = state.orders[question.id] || [];
    const starIndex = isOrderingQuestion(question) ? orderingStarIndex(question) : -1;
    const orderSummary = isOrderingQuestion(question) && order.length
      ? `<div class="submitted-order"><strong>你的排序：</strong>${order.map((value, position) => `${position === starIndex ? "★" : position + 1}=${value}`).join(" → ")}</div>` : "";
    const resultText = unanswered ? "未作答" : correct ? "回答正确" : "回答错误";
    const resultClass = correct ? "result-ok" : "result-bad";
    const explanation = card.querySelector(".explanation");
    explanation.innerHTML = `${orderSummary}<div class="single-check-result ${resultClass}">${resultText}</div><strong>正确答案：${expected.join("、")}</strong>${question.analysis ? `<br><br>${formatAnalysisHtml(question.analysis)}` : ""}${question.analysisSource ? `<small>解析来源：${escapeHtml(question.analysisSource)}</small>` : ""}`;
    explanation.hidden = false;

    const checkButton = card.querySelector("button[data-check-question]");
    if (checkButton) {
      checkButton.textContent = state.replayMode ? "历史回放" : state.submitted ? "已提交" : "重新判定本题";
      checkButton.disabled = state.submitted;
    }
    if (state.submitted) {
      const reasonInput = card.querySelector("textarea[data-reason-question]");
      if (reasonInput) reasonInput.readOnly = true;
      card.querySelectorAll("textarea[data-option-reason-question]").forEach((textarea) => { textarea.readOnly = true; });
    }
  }

  function showQuestionAnswer(questionId, { scroll = false } = {}) {
    if (state.submitted) return;
    const question = state.questions.find((item) => item.id === questionId);
    if (!question) return;
    const expected = expectedAnswers(question);
    const selected = selectedAnswers(question);
    const results = expected.map((answer, index) => Number(selected[index]) === answer);
    state.checked[questionId] = true;
    state.results[questionId] = results;
    renderQuestionFeedback(question, selected, expected, results);
    renderQuestionNav();
    if (scroll) $(`#question-${CSS.escape(questionId)} .explanation`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    saveUiState();
  }

  function submitExam() {
    if (state.submitted) return;
    const total = state.questions.reduce((sum, q) => sum + pointCount(q), 0);
    const answered = answeredPointCount();
    if (answered < total && !window.confirm(`还有 ${total - answered} 小题未作答，仍然提交吗？`)) return;

    state.submitted = true;
    clearInterval(state.timerId);
    const durationSeconds = Math.max(1, Math.round((Date.now() - state.startedAt) / 1000));
    let correct = 0;
    const details = [];

    state.questions.forEach((question, index) => {
      const expected = expectedAnswers(question);
      const selected = selectedAnswers(question);
      const results = expected.map((answer, i) => Number(selected[i]) === answer);
      state.results[question.id] = results;
      correct += results.filter(Boolean).length;
      const reason = String(state.reasons[question.id] || "").trim();
      const optionReasons = Object.fromEntries(Object.entries(state.optionReasons[question.id] || {})
        .map(([key, value]) => [key, String(value || "").trim()]).filter(([, value]) => value));
      details.push({
        sourceYear: PRACTICE.byId.get(question.id)?.year || state.year,
        sourceCategory: PRACTICE.byId.get(question.id)?.category || state.category,
        tags: [...(PRACTICE.annotations[question.id]?.tags || [])],
        id: question.id, number: question.number ?? index + 1, selected, expected, results, reason, optionReasons,
        order: [...(state.orders[question.id] || [])], starPosition: isOrderingQuestion(question) ? orderingStarIndex(question) + 1 : null,
        answerRevealedBeforeSubmit: Boolean(state.checked[question.id]),
        questionText: question.question || question.title || question.subQuestion || "",
        options: question.options || []
      });

      renderQuestionFeedback(question, selected, expected, results);
    });
    renderQuestionNav();

    const submittedAt = new Date().toISOString();
    const record = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      submittedAt,
      timezoneOffsetMinutes: new Date().getTimezoneOffset(),
      mode: state.practice ? "special" : "period",
      practice: state.practice,
      year: state.year,
      category: state.category,
      questionCount: state.questions.length,
      total,
      answered,
      correct,
      percentage: Math.round(correct / total * 100),
      durationSeconds,
      reasonCount: details.filter((detail) => detail.reason).length,
      optionReasonCount: details.reduce((sum, detail) => sum + Object.keys(detail.optionReasons).length, 0),
      details
    };
    const history = loadHistory();
    history.unshift(record);
    saveHistory(history);
    state.historyRecordId = record.id;

    $("#score-panel").innerHTML = `<h3>${correct} / ${total} · ${record.percentage} 分</h3><div>已答 ${answered} 小题，用时 ${formatDuration(durationSeconds)}。本次结果已保存到本地历史。</div>`;
    $("#score-panel").hidden = false;
    $("#submit-button").hidden = true;
    $("#submit-bottom-button").hidden = true;
    $("#score-panel").scrollIntoView({ behavior: "smooth", block: "center" });
    saveUiState();
  }

  function leaveExam() {
    const hasReason = Object.values(state.reasons).some((reason) => String(reason).trim());
    const hasOptionReason = Object.values(state.optionReasons).some((reasons) => Object.values(reasons || {}).some((reason) => String(reason).trim()));
    const hasOrder = Object.values(state.orders).some((order) => (order || []).length);
    if (!state.submitted && (answeredPointCount() || hasReason || hasOptionReason || hasOrder) && !window.confirm("当前答案、排序和答题理由尚未提交，确定返回吗？")) return;
    closeAiDrawer();
    clearInterval(state.timerId);
    const returnToHistory = state.replayMode;
    const returnToSpecial = Boolean(state.practice);
    state.practice = null;
    $("#exam-panel").hidden = true;
    $("#setup-panel").hidden = false;
    state.questions = [];
    state.answers = {};
    state.reasons = {};
    state.optionReasons = {};
    state.orders = {};
    state.results = {};
    state.checked = {};
    state.aiChats = {};
    state.replayMode = false;
    state.historyRecordId = null;
    saveUiState();
    if (returnToHistory) switchView("history");
    else if (returnToSpecial) switchView("special");
  }

  function lookupQuestion(record, detail) {
    const byId = PRACTICE.byId.get(detail.id);
    if (byId) return record.mode === "special" ? PRACTICE.question(detail.id) : byId.question;
    if (record.mode === "special") return null;
    const exam = DATA.exams?.[record.year] || {};
    const all = Object.values(exam).flat();
    const direct = all.find((question) => question.id === detail.id);
    if (direct) return direct;
    const categories = record.category === "文字・词汇" ? ["文字", "词汇"] : [record.category];
    return categories.flatMap((category) => exam[category] || [])
      .find((question) => String(question.number) === String(detail.number));
  }

  function locateQuestion(record, detail) {
    const byId = PRACTICE.byId.get(detail.id);
    if (byId) return byId;
    if (record.mode === "special") return null;
    const exam = DATA.exams?.[record.year] || {};
    for (const [category, questions] of Object.entries(exam)) {
      const direct = questions.find((question) => question.id === detail.id);
      if (direct) return { question: direct, category };
    }
    const categories = record.category === "文字・词汇" ? ["文字", "词汇"] : [record.category];
    for (const category of categories) {
      const question = (exam[category] || []).find((item) => String(item.number) === String(detail.number));
      if (question) return { question, category };
    }
    return null;
  }

  function normalizedHistoryCategory(value) {
    return ["文字", "词汇", "文字・词汇"].includes(value) ? "文字・词汇" : value;
  }

  function recordAccuracy(record) {
    const percentage = Number(record?.percentage);
    if (Number.isFinite(percentage)) return Math.max(0, Math.min(100, percentage));
    return Number(record?.total) ? Math.round(Number(record.correct || 0) / Number(record.total) * 100) : 0;
  }

  function renderInsights() {
    renderTagInsights();
    const target = $("#home-insights");
    if (!target) return;
    const history = loadHistory().filter((record) => record && Number(record.total) > 0);
    if (!history.length) {
      target.innerHTML = `<div class="insights-empty"><p class="section-kicker">学习概览</p><h2>完成一次练习后，这里会形成你的能力画像</h2><p>将显示总体正确率、各科表现、近期趋势和薄弱题型。</p></div>`;
      return;
    }

    const totals = history.reduce((sum, record) => ({
      correct: sum.correct + Number(record.correct || 0),
      total: sum.total + Number(record.total || 0),
      duration: sum.duration + Number(record.durationSeconds || 0),
    }), { correct: 0, total: 0, duration: 0 });
    const overall = totals.total ? Math.round(totals.correct / totals.total * 100) : 0;
    const studyDays = new Set(history.map((record) => {
      const date = new Date(record.submittedAt);
      return Number.isNaN(date.getTime()) ? String(record.submittedAt).slice(0, 10) : date.toLocaleDateString("sv-SE");
    })).size;
    const studyMinutes = Math.round(totals.duration / 60);

    const subjectStats = new Map(UI_CATEGORIES.map((category) => [category, { correct: 0, total: 0, attempts: 0 }]));
    history.forEach((record) => {
      if (record.mode === "special") {
        const attemptedSubjects = new Set();
        for (const detail of record.details || []) {
          const located = locateQuestion(record, detail);
          const subject = normalizedHistoryCategory(located?.category || detail.sourceCategory);
          const stat = subjectStats.get(subject);
          if (!stat) continue;
          const results = detail.results || [];
          stat.correct += results.filter(Boolean).length;
          stat.total += results.length;
          attemptedSubjects.add(subject);
        }
        attemptedSubjects.forEach((subject) => subjectStats.get(subject).attempts++);
        return;
      }
      const category = normalizedHistoryCategory(record.category);
      if (!subjectStats.has(category)) return;
      const stat = subjectStats.get(category);
      stat.correct += Number(record.correct || 0);
      stat.total += Number(record.total || 0);
      stat.attempts += 1;
    });

    const groupStats = new Map();
    history.forEach((record) => (record.details || []).forEach((detail) => {
      const located = locateQuestion(record, detail);
      if (!located) return;
      const category = normalizedHistoryCategory(located.category);
      const group = located.question.groupNumber || "?";
      const key = `${category} · 問題 ${group}`;
      const stat = groupStats.get(key) || { correct: 0, total: 0 };
      const results = Array.isArray(detail.results) ? detail.results : [];
      stat.correct += results.filter(Boolean).length;
      stat.total += results.length || 1;
      groupStats.set(key, stat);
    }));
    const weakGroups = [...groupStats.entries()]
      .filter(([, stat]) => stat.total >= 3)
      .map(([name, stat]) => ({ name, ...stat, percentage: Math.round(stat.correct / stat.total * 100) }))
      .sort((a, b) => a.percentage - b.percentage || b.total - a.total)
      .slice(0, 5);

    const recentChronological = [...history]
      .sort((a, b) => String(a.submittedAt).localeCompare(String(b.submittedAt)))
      .slice(-10);
    const recent = [...history]
      .sort((a, b) => String(b.submittedAt).localeCompare(String(a.submittedAt)))
      .slice(0, 5);

    target.innerHTML = `
      <div class="insights-heading"><div><p class="section-kicker">学习概览</p><h2>根据 ${history.length} 次提交生成</h2></div><p>统计范围：项目与浏览器中当前可见的全部历史记录</p></div>
      <div class="metric-grid">
        <div class="metric-card"><span>总体正确率</span><strong>${overall}%</strong><small>${totals.correct} / ${totals.total} 题</small></div>
        <div class="metric-card"><span>完成练习</span><strong>${history.length}</strong><small>次提交</small></div>
        <div class="metric-card"><span>学习天数</span><strong>${studyDays}</strong><small>个不同日期</small></div>
        <div class="metric-card"><span>累计用时</span><strong>${studyMinutes}</strong><small>分钟</small></div>
      </div>
      <div class="insights-grid">
        <section class="insight-card subject-performance"><h3>各科表现</h3>
          ${[...subjectStats.entries()].map(([category, stat]) => {
            const percentage = stat.total ? Math.round(stat.correct / stat.total * 100) : null;
            return `<div class="subject-row"><div><strong>${escapeHtml(category)}</strong><small>${stat.attempts ? `${stat.attempts} 次 · ${stat.correct}/${stat.total}` : "暂无记录"}</small></div><div class="subject-score">${percentage === null ? "—" : `${percentage}%`}</div><div class="progress-track"><span style="width:${percentage || 0}%"></span></div></div>`;
          }).join("")}
        </section>
        <section class="insight-card"><h3>最近正确率趋势</h3>
          <div class="trend-chart" aria-label="最近十次答题正确率">
            ${recentChronological.map((record) => {
              const percentage = recordAccuracy(record);
              return `<div class="trend-item" title="${escapeHtml(record.year)} · ${escapeHtml(record.category)}：${percentage}%"><span class="trend-value">${percentage}</span><div class="trend-column"><span style="height:${Math.max(4, percentage)}%"></span></div><small>${escapeHtml(String(record.year).slice(2))}</small></div>`;
            }).join("")}
          </div>
        </section>
        <section class="insight-card"><h3>优先复习的题型</h3>
          ${weakGroups.length ? `<div class="weak-list">${weakGroups.map((item) => `<div><span>${escapeHtml(item.name)}</span><strong class="${item.percentage < 60 ? "low-score" : ""}">${item.percentage}%</strong><small>${item.correct}/${item.total} 题</small></div>`).join("")}</div>` : `<p class="muted">完成更多题目后显示，单个题型至少需要 3 个作答点。</p>`}
        </section>
        <section class="insight-card"><h3>最近答题</h3>
          <div class="recent-list">${recent.map((record) => `<div><span><strong>${escapeHtml(record.year)} · ${escapeHtml(record.category)}</strong><small>${formatDate(record.submittedAt)}</small></span><strong class="recent-score">${recordAccuracy(record)}%</strong></div>`).join("")}</div>
        </section>
      </div>`;
  }

  function optionReasonMarkup(detail) {
    const entries = Object.entries(detail.optionReasons || {}).filter(([, value]) => String(value || "").trim());
    if (!entries.length) return "—";
    return entries.map(([key, value]) => {
      const [scope, option] = key.split(":");
      const prefix = scope === "main" ? `选项 ${option}` : `问题 ${Number(scope) + 1} · 选项 ${option}`;
      return `<div class="saved-option-reason"><strong>${escapeHtml(prefix)}</strong>：${escapeHtml(value)}</div>`;
    }).join("");
  }

  function savedOrderMarkup(detail) {
    const order = Array.isArray(detail.order) ? detail.order : [];
    if (!order.length) return "—";
    return order.map((optionNumber, position) => {
      const marker = position === Number(detail.starPosition || 3) - 1 ? "★" : String(position + 1);
      const label = detail.options?.[Number(optionNumber) - 1];
      return `<div class="saved-order-item"><strong>${marker}</strong><span>${escapeHtml(optionNumber)}${label ? `. ${escapeHtml(label)}` : ""}</span></div>`;
    }).join("");
  }

  async function copyQuestionId(button) {
    const value = button.dataset.copyQuestionId || "";
    if (!value) return;
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(value);
      else {
        const helper = document.createElement("textarea");
        helper.value = value;
        helper.style.position = "fixed";
        helper.style.opacity = "0";
        document.body.appendChild(helper);
        helper.select();
        document.execCommand("copy");
        helper.remove();
      }
      const icon = button.querySelector("span");
      if (icon) icon.textContent = "✓";
      button.classList.add("copied");
      button.title = `已复制：${value}`;
      window.setTimeout(() => {
        if (icon) icon.textContent = "⧉";
        button.classList.remove("copied");
        button.title = "复制题目 ID";
      }, 1600);
    } catch (_) {
      window.prompt("复制题目 ID：", value);
    }
  }

  function renderHistory() {
    const history = loadHistory();
    $("#history-count").textContent = history.length;
    const yearFilter = $("#history-year-filter");
    const categoryFilter = $("#history-category-filter");
    const selectedYear = yearFilter?.value || "";
    const selectedCategory = categoryFilter?.value || "";
    if (yearFilter) {
      const years = [...(history.some((record) => record.mode === "special") ? ["专项练习"] : []), ...DATA.years.filter((year) => history.some((record) => record.year === year))];
      yearFilter.innerHTML = `<option value="">全部期次</option>${years.map((year) => `<option value="${escapeHtml(year)}">${escapeHtml(year)}</option>`).join("")}`;
      if (years.includes(selectedYear)) yearFilter.value = selectedYear;
    }
    if (categoryFilter) {
      categoryFilter.innerHTML = `<option value="">全部科目</option>${UI_CATEGORIES.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join("")}`;
      if (UI_CATEGORIES.includes(selectedCategory)) categoryFilter.value = selectedCategory;
    }
    const activeYear = yearFilter?.value || "";
    const activeCategory = categoryFilter?.value || "";
    const filtered = history.filter((record) => {
      const yearMatches = !activeYear || record.year === activeYear;
      const categoryMatches = !activeCategory || normalizedHistoryCategory(record.category) === activeCategory
        || (record.mode === "special" && (record.details || []).some((detail) => normalizedHistoryCategory(locateQuestion(record, detail)?.category || detail.sourceCategory) === activeCategory));
      return yearMatches && categoryMatches;
    });
    $("#history-empty").hidden = filtered.length > 0;
    $("#history-empty p").textContent = history.length ? "没有符合当前筛选条件的记录。" : "还没有答题记录。";
    $("#history-filter-summary").textContent = `显示 ${filtered.length} / ${history.length} 条记录`;
    $("#history-list").innerHTML = filtered.map((record) => `
      <article class="history-row">
        <div><strong>${escapeHtml(record.mode === "special" ? practiceTitle(record.practice) : `${record.year} · ${record.category}`)}</strong><p class="muted">${formatDate(record.submittedAt)}</p></div>
        <div><p class="score-badge">${record.percentage} 分</p><p class="muted">${record.correct} / ${record.total}</p></div>
        <div><strong>${formatDuration(record.durationSeconds)}</strong><p class="muted">答题用时</p></div>
        <div><strong>${record.answered} / ${record.total}</strong><p class="muted">完成度</p></div>
        <button class="secondary-button" data-history-id="${record.id}">查看详情</button>
      </article>`).join("");
  }

  function loadHistoryIntoExam(id, { restoring = false } = {}) {
    const record = loadHistory().find((item) => item.id === id);
    if (!record) return;
    closeAiDrawer();
    clearInterval(state.timerId);
    const pairs = [];
    const usedIds = new Set();
    (record.details || []).forEach((detail) => {
      const current = lookupQuestion(record, detail);
      if (!current || usedIds.has(current.id)) return;
      usedIds.add(current.id);
      pairs.push({
        detail,
        question: current,
      });
    });
    if (!pairs.length) {
      window.alert("这条历史记录缺少可回放的逐题数据。");
      return;
    }

    state.practice = record.mode === "special" ? record.practice || { filters: {}, questionIds: pairs.map(({ question }) => question.id) } : null;
    state.year = record.year;
    state.category = normalizedHistoryCategory(record.category);
    state.questions = pairs.map((pair) => pair.question);
    state.answers = {};
    state.reasons = {};
    state.optionReasons = {};
    state.orders = {};
    state.results = {};
    state.checked = {};
    state.aiChats = {};
    state.submitted = true;
    state.replayMode = true;
    state.historyRecordId = id;
    state.startedAt = Date.now() - Number(record.durationSeconds || 0) * 1000;

    pairs.forEach(({ question, detail }) => {
      const selected = Array.isArray(detail.selected) ? detail.selected : [detail.selected ?? null];
      state.answers[question.id] = selected.length > 1 ? [...selected] : selected[0];
      state.reasons[question.id] = detail.reason || "";
      state.optionReasons[question.id] = { ...(detail.optionReasons || {}) };
      state.orders[question.id] = [...(detail.order || [])];
      state.results[question.id] = Array.isArray(detail.results) ? [...detail.results] : [];
      state.checked[question.id] = Boolean(detail.answerRevealedBeforeSubmit);
    });

    switchView("practice");
    $("#setup-panel").hidden = true;
    $("#exam-panel").hidden = false;
    $("#exam-title").textContent = `历史回放 · ${state.practice ? practiceTitle(state.practice) : `${record.year} · ${record.category}`}`;
    $("#back-button").textContent = "← 返回答题历史";
    $("#submit-button").hidden = true;
    $("#submit-bottom-button").hidden = true;
    $("#score-panel").innerHTML = `<h3>${record.correct} / ${record.total} · ${record.percentage} 分</h3><div>${formatDate(record.submittedAt)} 提交，用时 ${formatDuration(record.durationSeconds)}。当前为历史回放，不会修改原记录。</div>`;
    $("#score-panel").hidden = false;
    $("#timer").textContent = formatDuration(Number(record.durationSeconds || 0));
    $("#answer-progress").textContent = `已答 ${record.answered} / ${record.total}`;

    const seenPassages = new Set();
    $("#questions-form").innerHTML = state.questions.map((question, index) => questionMarkup(question, index, seenPassages)).join("");
    pairs.forEach(({ question, detail }) => {
      if (isOrderingQuestion(question)) renderOrderingControl(question.id);
      const card = $(`#question-${CSS.escape(question.id)}`);
      const selected = Array.isArray(detail.selected) ? detail.selected : [detail.selected ?? null];
      card.querySelectorAll("input[data-question]").forEach((input) => {
        const position = input.dataset.sub === undefined ? 0 : Number(input.dataset.sub);
        input.checked = Number(input.value) === Number(selected[position]);
      });
      const reasonInput = card.querySelector("textarea[data-reason-question]");
      if (reasonInput) reasonInput.value = detail.reason || "";
      card.querySelectorAll("textarea[data-option-reason-key]").forEach((textarea) => {
        textarea.value = detail.optionReasons?.[textarea.dataset.optionReasonKey] || "";
      });
      const expected = Array.isArray(detail.expected) ? detail.expected : expectedAnswers(question);
      const results = Array.isArray(detail.results) && detail.results.length
        ? detail.results : expected.map((answer, index) => Number(selected[index]) === Number(answer));
      renderQuestionFeedback(question, selected, expected, results);
    });
    renderQuestionNav();
    window.scrollTo({ top: 0, behavior: restoring ? "auto" : "smooth" });
    saveUiState();
  }

  function restoreUiState() {
    const saved = loadUiState();
    if (!saved || saved.version !== 1) {
      saveUiState();
      return;
    }
    restoringUiState = true;
    if (DATA.years.includes(saved.year)) $("#year-select").value = saved.year;
    if (UI_CATEGORIES.includes(saved.category)) $("#category-select").value = saved.category;
    refreshYearOptions();
    updateSelectionSummary();
    restoreSpecialFilters(saved.specialFilters || {});
    $("#special-count").value = saved.specialCount || "10";
    updateSpecialSummary();

    if (saved.historyYear) $("#history-year-filter").value = saved.historyYear;
    if (UI_CATEGORIES.includes(saved.historyCategory)) $("#history-category-filter").value = saved.historyCategory;
    renderHistory();

    const view = ["practice", "special", "history", "ai-config"].includes(saved.view) ? saved.view : "practice";
    if (saved.examActive) {
      const recordExists = saved.historyRecordId && loadHistory().some((record) => record.id === saved.historyRecordId);
      if ((saved.replayMode || saved.submitted) && recordExists) {
        loadHistoryIntoExam(saved.historyRecordId, { restoring: true });
      } else {
        switchView("practice");
        startExam(saved.draft || null);
      }
    } else {
      switchView(view);
    }
    if (view !== "practice") switchView(view);
    restoreScrollPosition(saved);
  }

  function showHistoryDetail(id) {
    const record = loadHistory().find((item) => item.id === id);
    if (!record) return;
    $("#history-detail").innerHTML = `
      <p class="section-kicker">${escapeHtml(record.year)} · ${escapeHtml(record.category)}</p>
      <h2>${record.percentage} 分</h2>
      <p>${formatDate(record.submittedAt)}</p>
      <div class="detail-grid">
        <div><strong>${record.correct} / ${record.total}</strong><br>正确</div>
        <div><strong>${record.answered} / ${record.total}</strong><br>已答</div>
        <div><strong>${formatDuration(record.durationSeconds)}</strong><br>用时</div>
      </div>
      <table class="detail-table"><thead><tr><th>题号</th><th>作答</th><th>我的排序</th><th>正确答案</th><th>结果</th><th>提交前看答案</th><th>题目理由</th><th>选项理由</th><th>答案解析</th></tr></thead><tbody>
      ${record.details.map((detail) => {
        const question = lookupQuestion(record, detail);
        const analysis = question?.analysis || "暂无解析";
        const source = question?.analysisSource || "";
        return `<tr><td>${escapeHtml(detail.number)}</td><td>${detail.selected.map((v) => v ?? "—").join("、")}</td><td class="order-detail">${savedOrderMarkup(detail)}</td><td>${detail.expected.join("、")}</td><td class="${detail.results.every(Boolean) ? "result-ok" : "result-bad"}">${detail.results.every(Boolean) ? "正确" : "错误"}</td><td>${detail.answerRevealedBeforeSubmit ? "是" : "否"}</td><td class="reason-detail">${escapeHtml(detail.reason || "—")}</td><td class="option-reasons-detail">${optionReasonMarkup(detail)}</td><td class="analysis-detail">${formatAnalysisHtml(analysis)}${source ? `<small>来源：${escapeHtml(source)}</small>` : ""}</td></tr>`;
      }).join("")}
      </tbody></table>`;
    $("#history-dialog").showModal();
  }

  function exportHistory() {
    const blob = new Blob([JSON.stringify({ version: 2, exportedAt: new Date().toISOString(), history: loadHistory() }, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `N1答题历史-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function importHistory(file) {
    try {
      const parsed = JSON.parse(await file.text());
      if (!parsed || !Array.isArray(parsed.history)) throw new Error("格式不正确");
      const existing = loadHistory();
      const byId = new Map([...existing, ...parsed.history].map((item) => [item.id, item]));
      saveHistory([...byId.values()].sort((a, b) => String(b.submittedAt).localeCompare(String(a.submittedAt))));
      window.alert("历史记录导入完成。相同记录已自动去重。");
    } catch (error) {
      window.alert(`导入失败：${error.message}`);
    }
  }

  $$(".tab").forEach((tab) => tab.addEventListener("click", () => switchView(tab.dataset.view)));
  $("#year-select").addEventListener("change", () => {
    updateSelectionSummary();
    saveUiState();
  });
  $("#category-select").addEventListener("change", () => {
    refreshYearOptions();
    updateSelectionSummary();
    saveUiState();
  });
  $("#start-button").addEventListener("click", () => startExam());
  $("#back-button").addEventListener("click", leaveExam);
  $("#submit-button").addEventListener("click", submitExam);
  $("#submit-bottom-button").addEventListener("click", submitExam);
  $("#questions-form").addEventListener("change", (event) => {
    const input = event.target.closest("input[data-question]");
    if (!input || state.submitted) return;
    const id = input.dataset.question;
    if (input.dataset.sub === undefined) state.answers[id] = Number(input.value);
    else {
      const answers = Array.isArray(state.answers[id]) ? state.answers[id] : [null, null];
      answers[Number(input.dataset.sub)] = Number(input.value);
      state.answers[id] = answers;
    }
    updateProgress();
    if (state.checked[id]) showQuestionAnswer(id);
    else renderQuestionNav();
    saveUiState();
  });
  $("#questions-form").addEventListener("input", (event) => {
    if (state.submitted) return;
    const optionTextarea = event.target.closest("textarea[data-option-reason-question]");
    if (optionTextarea) {
      const id = optionTextarea.dataset.optionReasonQuestion;
      state.optionReasons[id] ||= {};
      state.optionReasons[id][optionTextarea.dataset.optionReasonKey] = optionTextarea.value;
      saveUiState();
      return;
    }
    const textarea = event.target.closest("textarea[data-reason-question]");
    if (textarea) {
      state.reasons[textarea.dataset.reasonQuestion] = textarea.value;
      saveUiState();
    }
  });
  $("#questions-form").addEventListener("click", (event) => {
    const aiOpenButton = event.target.closest("button[data-ai-open]");
    if (aiOpenButton) {
      openAiDrawer(aiOpenButton.dataset.aiOpen);
      return;
    }
    const copyButton = event.target.closest("button[data-copy-question-id]");
    if (copyButton) {
      copyQuestionId(copyButton);
      return;
    }
    const checkButton = event.target.closest("button[data-check-question]");
    if (checkButton) {
      showQuestionAnswer(checkButton.dataset.checkQuestion, { scroll: true });
      return;
    }
    if (state.submitted) return;
    const button = event.target.closest("button[data-order-add], button[data-order-move], button[data-order-remove], button[data-order-reset]");
    if (!button) return;
    const control = button.closest("[data-order-question]");
    const questionId = control?.dataset.orderQuestion;
    if (!questionId) return;
    const order = [...(state.orders[questionId] || [])];
    if (button.matches("[data-order-add]")) {
      const optionNumber = Number(button.dataset.orderAdd);
      if (order.length < 4 && !order.includes(optionNumber)) order.push(optionNumber);
    } else if (button.matches("[data-order-move]")) {
      const from = Number(button.dataset.orderIndex);
      const to = from + Number(button.dataset.orderMove);
      if (from >= 0 && to >= 0 && to < order.length) [order[from], order[to]] = [order[to], order[from]];
    } else if (button.matches("[data-order-remove]")) {
      order.splice(Number(button.dataset.orderRemove), 1);
    } else {
      order.length = 0;
    }
    state.orders[questionId] = order;
    syncOrderingAnswer(questionId);
    saveUiState();
  });
  $("#ai-drawer-send").addEventListener("click", () => {
    if (activeAiQuestionId) sendAiQuestion(activeAiQuestionId);
  });
  $("#ai-drawer-clear").addEventListener("click", () => {
    if (!activeAiQuestionId) return;
    if (activeAiRequest) stopAiGeneration("已停止生成");
    state.aiChats[activeAiQuestionId] = [];
    renderAiChat(activeAiQuestionId);
    setAiChatStatus(activeAiQuestionId, "");
  });
  $("#ai-drawer-close").addEventListener("click", closeAiDrawer);
  $("#ai-drawer-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      if (activeAiQuestionId) sendAiQuestion(activeAiQuestionId);
    }
  });
  $("#question-nav").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-nav-question]");
    if (!button) return;
    document.getElementById(`question-${button.dataset.navQuestion}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("#history-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-history-id]");
    if (button) loadHistoryIntoExam(button.dataset.historyId);
  });
  $("#history-year-filter").addEventListener("change", () => { renderHistory(); saveUiState(); });
  $("#history-category-filter").addEventListener("change", () => { renderHistory(); saveUiState(); });
  $("#dialog-close").addEventListener("click", () => $("#history-dialog").close());
  $("#export-button").addEventListener("click", exportHistory);
  $("#import-input").addEventListener("change", (event) => event.target.files[0] && importHistory(event.target.files[0]));
  $("#save-gemini-key").addEventListener("click", saveGeminiConfig);
  window.addEventListener("resize", () => positionAiDrawer());
  window.addEventListener("scroll", () => {
    positionAiDrawer();
    window.clearTimeout(scrollSaveTimer);
    scrollSaveTimer = window.setTimeout(saveUiState, 120);
  }, { passive: true });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && activeAiQuestionId) closeAiDrawer();
  });
  window.addEventListener("beforeunload", saveUiState);
  $$('[data-go-practice]').forEach((button) => button.addEventListener("click", () => switchView("practice")));

  if (!DATA || !DATA.exams) {
    document.body.innerHTML = "<p>题库数据未生成，请先运行根目录下的 build_offline_exam.py。</p>";
    return;
  }
  initSpecialSelectors();
  initSelectors();
  renderHistory();
  renderInsights();
  restoreUiState();
  initializeProjectStorage();
  refreshAiConfigStatus();
})();
