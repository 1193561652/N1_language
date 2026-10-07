# 句子构成题的上方假名

范围：语法問題5「句子语法」310题和問題6「句子排序」155题，共465题。提交后与历史回放默认在题干、选项、已排列片段上显示振假名，每张题卡可显示或隐藏。提前检查单题答案不会显示。中文解析、个人答题理由和其他题型不处理。

读音保存在 `ordering-furigana.json`，按题目ID和精确原文关联，随根目录 `index.html` 内嵌，直接双击和本地服务均无需联网。原文改变时对应文本回退为无注音，避免把旧读音套到新句子。原题已有的括号读音保留，且优先用于上方注音。

维护时安装 `requirements-furigana.txt`，运行 `build_ordering_furigana.py` 重新生成。使用 SudachiPy 与固定版本的核心词典，并在生成器中维护上下文校对项。自动读音不代表每个专有名词均已人工确认；原题OCR误字也不会被此功能改写。

正常完整构建仍使用 `build_offline_exam.py`。只更新界面、需要保留当前题库和专项数据时，使用 `build_offline_exam.py --bundle-only`；此模式不重新导入题目、不刷新专项映射，也不绕过完整构建的来源校验。

验证：

```text
node offline-exam-tool/tests/test_ordering_furigana.js
node offline-exam-tool/tests/test_ordering_furigana_browser.js
```

浏览器测试需要 Playwright 和 Edge，可用环境变量 `PLAYWRIGHT_MODULE` 指定已有的 Playwright 模块；可选 `FURIGANA_SCREENSHOT` 指定桌面与手机截图路径。测试使用独立浏览器上下文和本地文件页面，不写项目答题历史。

2026-10-05 验证：465题文本及汉字覆盖检查、专项练习JS回归检查通过。原問題6已验证2022.12/2024.07/2025.12提交与回放；補充問題5后，直接在localhost页面验证当日17:49的10题历史，全部出现假名开关，题干及选项显示上方假名，隐藏/显示与刷新回放正常。完整构建及全局检查仍受到既有题库与审核指纹不一致、2025.12第28题和2025.07第26/29题解析格式检查失败影响。本功能用当前题库重新打包，没有修改这些题目。
