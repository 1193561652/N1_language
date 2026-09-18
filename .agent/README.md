# N1 项目 Agent 导航

本目录保存项目级上下文和维护导航，供后续人工维护或自动化任务快速理解仓库。这里不存放题目正文、登录凭据、浏览器令牌或答题记录。

## 从这里开始

1. 阅读 [PROJECT.md](PROJECT.md)，了解项目目标、数据范围和主要组成。
2. 阅读 [NAVIGATION.md](NAVIGATION.md)，按任务找到正确目录和入口。
3. 修改离线题库前阅读 [OFFLINE_EXAM.md](OFFLINE_EXAM.md)，并在完成后执行构建与校验。

## 核心入口

- 离线答题入口：`E:\N1_language\index.html`
- 离线题库工具：`E:\N1_language\offline-exam-tool`
- 项目总说明：`E:\N1_language\README.md`
- 真题索引：`E:\N1_language\08 Past Papers\Past Paper Index.md`

## 维护原则

- 根目录的 `index.html` 是最终用户入口；工具文件集中放在 `offline-exam-tool`，不要再次散落到根目录。
- `library2` 是原始资源库，未经明确要求不要改名、移动或覆盖其中的文件。
- 抓取站点的数据保留在各自目录：`Shaobing Japanese` 与 `JLPT4YOU`。
- 转换、OCR 和 Markdown 产物保留在 `output`，不要与原始资源混放。
- 认证文件属于敏感数据，不读取、不展示、不写入文档或日志。
- 通过项目启动器答题时，每次提交会在 `offline-exam-tool\history\records` 生成一个独立历史文件；浏览器存储只是缓存。
