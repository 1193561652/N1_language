# 离线题库上方假名

当前范围：语法問題5（310题）及所有阅读题（31期，共752题）。阅读覆盖大题说明、共享文章、题干和选项，沿用文法的汉字上方假名样式、首页显示选择、提交及历史回放的逐题显示/隐藏开关。仅提前检查单题答案不会自动开启。中文解析与个人答题理由不处理。

读音保存在 `ordering-furigana.json`，按题目ID和精确原文关联，随根目录 `index.html` 内嵌，双击打开及本地服务均无需联网。原文改变时对应文本回退为无注音。保留原题括号读音与下划线。

维护依赖见 `requirements-furigana.txt`；运行 `build_ordering_furigana.py` 后运行 `build_offline_exam.py --bundle-only` 可用现有题库重新打包。常规完整构建仍可使用 `build_offline_exam.py`。使用 SudachiPy 与固定版本核心词典；生成器的 OCR_READINGS 为源文异常字补充上下文读音，不改写原题。自动注音及个别 OCR 严重损坏的文本不能视为人工校订版。

验证：

```text
node offline-exam-tool/tests/test_ordering_furigana.js
node offline-exam-tool/tests/test_reading_furigana_browser.js
node offline-exam-tool/tests/test_special_practice.js
```

2026-10-20：1062题精确原文和全部汉字读音覆盖检查通过；阅读的2022.12、2024.07、2025.12三种来源已通过浏览器检查，覆盖答题前隐藏、单题检查、提交、选项注音、显示/隐藏、历史回放及刷新。专项练习回归通过。全局校验仍报告既有的2025.12第28题、2025.07第26/27/29题解析格式问题，与本次假名变更无关。
