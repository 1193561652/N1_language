# 烧饼日语真题抓取器

`scrape_sbry.py` 使用烧饼日语网页版当前公开的前端接口结构，将本人有权访问的真题保存为 UTF-8 JSON。密码通过交互式提示读取，只在内存中做网页同款的 MD5 处理，不会写入文件。

## 使用方法

先查看当前可用年份（无需登录）：

```powershell
python .\scrape_sbry.py --level n1 --list
```

抓取一期用于验证：

```powershell
python .\scrape_sbry.py --level n1 --years 2022.12
```

没有用户名和密码时，可使用烧饼日语 App 扫码登录：

```powershell
python -m pip install --target .deps qrcode
python .\scrape_sbry.py --qr-login --level n1 --years 2022.12
```

二维码只在终端显示，扫码返回的临时令牌仅保存在当前进程内，不读取或导出浏览器登录数据。

默认情况下，成功登录后的令牌会保存到 `.sbry_auth.dpapi`。该文件使用 Windows DPAPI 加密，只能由当前 Windows 用户解密；后续运行会自动复用并验证令牌。使用 `--no-auth-cache` 可禁用缓存。令牌失效时，脚本会提示重新扫码。

抓取过程中每补全 10 道解析就会保存一次进度。重新运行相同命令会从已有 `exam.json` 继续，不会重新抓取已经完成的题目。

抓取 N1 全部年份，并下载题目引用的图片、逐题听力和整套听力：

```powershell
python .\scrape_sbry.py --level n1 --years all --download-assets
```

抓取完成后可运行完整性校验：

```powershell
python .\verify_scrape.py
```

用户名可通过 `--username` 传入，或预先设置 `SBRY_USERNAME`。密码始终由隐藏输入提示读取。默认会补全逐题解析；如只需要题目主数据，可加 `--skip-analysis`。已存在的年份默认跳过，使用 `--force` 可刷新。

输出目录为 `data/<等级>/<年份>/`：

- `exam.json`：按网页原始层级保存的题目、选项、答案与解析。
- `assets.json`：远程资源 URL 到本地文件的映射。
- `assets/images/`：图片。
- `assets/audio/`：听力音频。

请仅抓取本人账号有权访问的内容，遵守网站服务条款和版权要求。脚本默认在请求之间等待 0.25 秒，可用 `--delay` 调大间隔。

## 离线答题应用

双击 `启动离线题库.cmd`，程序会在默认浏览器中打开离线题库。运行期间不需要互联网连接，但启动窗口需要保持打开。

也可以手动运行：

```powershell
python .\start_offline_exam.py
```

应用支持按期次和文字、词汇、语法、阅读、听力分别答题，提交后立即判分。每次提交的日期、时间、用时、分数和逐题结果均保存在当前浏览器的本地存储中，并可在“答题历史”中查看。建议定期使用“导出备份”保存历史记录；清除浏览器网站数据会删除尚未导出的记录。

原始真题更新后，重新生成离线数据包：

```powershell
python .\build_offline_app.py
```
