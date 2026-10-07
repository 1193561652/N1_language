/* Readings are exact-text keyed so edited questions never receive stale ruby. */
(() => {
  'use strict';
  window.OrderingFurigana = {
    render(questionId, text, submitted, formatText) {
      const tokens = window.ORDERING_FURIGANA?.[questionId]?.[text];
      if (!submitted || !tokens || tokens.map(t => t[0]).join('') !== text) return formatText(text);
      return tokens.map(([base, reading]) => reading
        ? `<ruby class="ordering-ruby">${formatText(base)}<rt>${formatText(reading)}</rt></ruby>`
        : formatText(base)).join('');
    }
  };
})();
