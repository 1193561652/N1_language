# JLPT4YOU N1 真题原始资源

`scrape_jlpt4you.py` 按 JLPT4YOU 网页当前使用的公开同源接口下载 N1 官方真题。接口不需要账号凭据，因此脚本不会读取或保存用户名、密码、Cookie 或浏览器令牌。

当前数据范围为 2010.12 至 2024.12，共 28 期（2020.07 因考试取消而不存在）。站点的 N1 列表页可能只渲染到 2020.12，因此脚本以已验证可用的题目接口为准，不以页面上可见的旧列表为准。

抓取一期并下载媒体：

```powershell
python .\scrape_jlpt4you.py --years 2019.12 --download-assets
```

抓取网站当前列出的全部 N1 真题：

```powershell
python .\scrape_jlpt4you.py --years all --download-assets
```

输出位于 `data/n1/<年份>/`：

- `exam.json`：网站接口返回的原始题目结构，包含科目、大题、选项和答案。
- `assets.json`：远程媒体 URL 到本地文件的映射。
- `asset_errors.json`：源站不存在或重试后仍无法下载的媒体 URL。
- `assets/audio/`、`assets/images/`：听力和题目图片。

答案使用接口原始的零基索引：`0` 表示第一个选项，`3` 表示第四个选项。请仅将下载内容用于本人有权进行的学习和研究，并遵守网站服务条款及版权要求。

抓取完成后可重复运行完整性校验：

```powershell
python .\verify_jlpt4you.py
```

校验会检查全部期次、答案索引、媒体清单和本地文件，并生成 `verification_report.json`。报告中的 `warnings` 表示源站自身的数据缺项；`errors` 才表示本地抓取结果不一致。

## N1 模拟试题

站点当前提供 173 套 JLPT4YOU 自编 N1 模拟题。它们与官方真题分开保存于 `data/n1/mock/`：

```powershell
# 抓取全部题目 JSON
python .\scrape_jlpt4you_mock.py --exams all

# 下载全部题目和媒体（可断点续传）
python .\scrape_jlpt4you_mock.py --exams all --download-assets

# 只抓取第 1 至 5 套
python .\scrape_jlpt4you_mock.py --exams 1-5 --download-assets
```

`--workers` 控制媒体并发数，默认 4、最大 8。重复运行时已存在的有效文件会自动跳过。173 套试卷会共享 `data/n1/mock/assets/` 媒体目录并按 URL 去重，各套目录中的 `assets.json` 指向共享文件，避免重复保存数千份相同音频。

`source_index.json` 保存站点列表接口给出的路由编号，`index.json` 同时保存路由编号和题目响应内的真实编号。源站在第 122 套之后存在编号偏移，两者均保留以免丢失或错误覆盖试卷。

模拟题完整性校验：

```powershell
python .\verify_jlpt4you_mock.py
```

结果写入 `mock_verification_report.json`。
