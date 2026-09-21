# 项目导航

## 按任务查找

| 想做的事 | 首选位置 | 说明 |
| --- | --- | --- |
| 直接进行离线答题 | `index.html` | 双击打开；不要单独移出根目录 |
| 进行专项练习 | 首页或顶部导航“专项练习” | 文字・词汇/语法 → 問題及名称 → 考点；默认随机10题 |
| 维护专项练习题池 | `offline-exam-tool/build_practice_data.py` | 读取已审核标签映射并关联原题，新增标注后重建即可 |
| 修改统一答题界面 | `offline-exam-tool/app.js`、`styles.css`、`index.template.html` | 普通与专项共用答题、提交和回放流程 |
| 重建统一离线 HTML | `offline-exam-tool\build_offline_exam.py` | 合并三类来源并生成根目录入口 |
| 校验统一题库 | `offline-exam-tool\verify_offline_exam.py` | 检查期次、题量、答案、ID 和媒体文件 |
| 生成近十期逐题解析 | `offline-exam-tool\build_explanations.py` | 质量检查本地解析并以生成解析补齐 |
| 查看解析覆盖 | `offline-exam-tool\explanations\coverage.json` | 每期来源解析与生成解析数量 |
| 审计生成解析质量 | `offline-exam-tool\audit_ai_explanations.py` | 输出逐题问题清单到 `explanations\quality-audit.json` |
| 用本地服务器打开 | `offline-exam-tool\start_offline_exam.py` | 浏览器限制本地媒体时使用 |
| 启动项目记录模式 | `offline-exam-tool\启动离线题库.cmd` | 双击启动；提交记录写入项目 JSON |
| 配置逐题 AI 对话 | 页面顶部“AI 配置” | Key 写入 `offline-exam-tool\config\gemini.json`，不要提交或传播 |
| 查看统一校验结果 | `offline-exam-tool\offline_exam_verification.json` | 最近一次构建的机器可读报告 |
| 维护烧饼日语抓取 | `Shaobing Japanese` | 抓取器、验证器、原始结构化数据和媒体 |
| 维护 JLPT4YOU 抓取 | `JLPT4YOU` | 官方真题与模拟题抓取器、数据和验证报告 |
| 查找原始 PDF、答案、MP3 | `library2` | 原始资源，尽量只读 |
| 查找 OCR/Markdown 结果 | `output` | 各阶段转换与修复产物 |
| 查看真题总索引 | `08 Past Papers\Past Paper Index.md` | 真题覆盖和处理状态 |
| 查看文字词汇分类及逐题标签 | `output/N1考试知识库/文字词汇分类/README.md` | 正式商定分类；775题全覆盖，标签不得跨問題1—4 |
| 查看语法分类及逐题标签 | `output/N1考试知识库/语法分类/README.md` | 商定分类；全部31期609题，标签不得跨問題5—7 |
| 维护文字词汇标签 | `tools/language_tag_annotations.py`、`tools/build_language_taxonomy.py` | 显式逐题标注；生成后用 `--check` 校验范围、覆盖及源题一致性 |
| 维护 PDF 转换流程 | `gemini_pdf_to_markdown.py`、`tools` | 转换主脚本和辅助工具 |

## 重要子目录

### `offline-exam-tool`

- `build_offline_exam.py`：读取烧饼、JLPT4YOU 和本地 Markdown，生成统一数据与根目录 `index.html`。
- `index.template.html`：离线页面模板。
- `data.js`：构建后的结构化题库副本，位于工具目录，不是根目录入口依赖。
- `verify_offline_exam.py`：统一题库验收脚本。
- `build_explanations.py`：生成 2025.12 向前十期解析覆盖，并筛选本地解析资料。
- `explanations`：按期保存解析覆盖层和覆盖率报告。
- `offline_exam_verification.json`：校验报告。
- `start_offline_exam.py`：可选的 localhost 静态服务器。
- `history\records`：每次提交生成一个以期次、科目、提交时间命名的 JSON。
- `config\gemini.json`：用户在页面保存后生成的本地 Gemini API Key 文件；属于敏感配置，不应读取、复制或传播。

### `JLPT4YOU`

- `scrape_jlpt4you.py`：官方真题抓取。
- `scrape_jlpt4you_mock.py`：模拟题抓取。
- `verify_jlpt4you.py`、`verify_jlpt4you_mock.py`：抓取结果验证。
- `data`：按级别和期次保存的结构化题目及媒体。

### `Shaobing Japanese`

- `scrape_sbry.py`：题库抓取。
- `verify_scrape.py`：抓取完整性验证。
- `data`：结构化题目、图片和音频。
- `offline-exam`：早期离线页面的前端代码，作为历史版本保留；当前统一入口使用 `offline-exam-tool` 内的应用逻辑和样式。
- `.sbry_auth.dpapi`：敏感认证材料，不应读取或传播。

### `output`

主要保存 PDF/OCR/视觉识别生成的中间与最终文本。统一题库使用的 2025 Markdown 位于：

```text
output\AI易读Markdown归档\真题Markdown\2025
```

## 根目录约定

根目录用于项目入口、总说明、原始历史 PDF 和稳定一级目录。离线答题工具的脚本、模板、数据副本和报告必须保留在 `offline-exam-tool`，根目录只保留最终 `index.html`。
