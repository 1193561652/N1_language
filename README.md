# N1 Language System

目标不是只通过 JLPT N1, 而是建立一套长期维护的现代日语知识体系。

项目结构、数据来源、任务导航和离线题库维护说明见 [`.agent/README.md`](.agent/README.md)。

学习路径:

Scene -> Expression -> Vocabulary -> Grammar -> Listening / Reading -> JLPT

## Source Policy

内容来源优先级:

1. JLPT 官方样题与官方问题集
2. 用户上传的历年 N1 真题
3. NHK
4. 日本政府公开资料
5. 日本企业公开资料
6. Weblio / goo 辞書
7. 日本语料库, 如 BCCWJ

课程中的素材分为三类:

- Source-derived: 直接来自可验证来源, 会标明来源。
- Source-informed: 根据多个来源整理出的语言规律, 会标明依据。
- Teaching rewrite: 为教学目的改写或原创的句子, 必须标明为教学改写。

## Database Folders

- `01 Lessons`: 正式课程
- `02 Vocabulary`: 词汇卡
- `03 Collocations`: 固定搭配
- `04 Grammar`: 文法点
- `05 Listening`: 听力素材与脚本
- `06 Reading`: 阅读素材
- `07 Corpus`: 语料索引
- `08 Past Papers`: 真题索引与抽取结果
- `09 Review`: 间隔复习计划
- `10 Exercises`: 练习题库

N1 阅读长期训练的当前状态、升级标准和逐轮证据保存在 [`06 Reading/N1-Structured-Training`](06%20Reading/N1-Structured-Training/README.md)。

## Past Paper Workflow

上传真题后的处理流程:

Extract -> Classify -> Count -> Enter Lesson -> Update Database

当前上传的真题 PDF 多数需要 OCR 后才能自动统计词频、搭配和题型。未完成 OCR 前, 课程中的 JLPT Analysis 只记录可确认的考试形式与待验证项目, 不伪造频次。

## Offline Exam

项目根目录的 `index.html` 是统一的 N1 离线答题入口，当前包含 31 个期次：

- 烧饼日语：2010.07–2022.12
- JLPT4YOU 增量：2023.07–2024.12
- 本地 PDF→Markdown：2025.07、2025.12

页面可按期次及“文字・词汇”、语法、阅读、听力单科答题。首页会根据历史记录生成学习概览与薄弱题型统计。答题页提供带状态的题目目录；每题可单独判定并显示解析而不提交，语法排序题可排列完整选项，并保存用户排序供后续分析。每张题卡显示可一键复制的唯一 ID，每题及每个选项都可填写答题理由。整科提交后会判分并显示解析；项目启动模式下，每次提交会把日期、时间、耗时、逐题结果、排序、是否提前查看答案、理由和解析快照写入一个独立 JSON。历史页支持按期次和科目筛选，并可在原答题界面只读回放；记录也可导入/导出。

```powershell
# 生成或更新 2025.12 向前十期解析
python .\offline-exam-tool\build_explanations.py

# 源数据变化后重新构建
python .\offline-exam-tool\build_offline_exam.py

# 校验题量、答案、重复 ID 和本地媒体文件
python .\offline-exam-tool\verify_offline_exam.py

# 可选：启动本地服务器，然后访问 http://localhost:8765/
python .\offline-exam-tool\start_offline_exam.py
```

`index.html` 已内嵌题库数据、样式和程序代码，可以直接双击打开；但浏览器不允许本地 HTML 自动写项目文件，因此双击模式的记录只保存在浏览器。需要将记录保存到项目时，双击 `offline-exam-tool\启动离线题库.cmd`，或运行 `python .\offline-exam-tool\start_offline_exam.py`。每次提交会在 `offline-exam-tool\history\records` 中生成一个独立 JSON，文件名为“期次+科目+提交时间”。图片和 MP3 按相对路径读取，请勿单独移动 `index.html`。

2025 年的本地 Markdown 没有逐题切分的听力音频，因此每期听力第一题提供整场 MP3；答案和 30 个听力作答点已录入。

## 工作空间与版本管理

当前工作空间为 E:\N1_language。资料目录保持原有结构，所有后续维护在此目录进行。

Git 包含课程、题库、原始资料与处理产物；虚拟环境、临时文件、日志、个人答题历史及本地认证配置仅保存在本机。Gemini 转换工具优先读取 GEMINI_API_KEY 环境变量，也兼容 local-config 中的本地密钥文件。

