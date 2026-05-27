# 环境修复学习记录

## 2026-04-03 00:24:00 - 初始发现
- Windows PowerShell 5.1 环境
- winget 包管理器可用 (v1.28.220) - 可用于安全安装工具
- 桌面主要包含快捷方式，无显著代码项目
- glob/grep 工具失败原因为缺少 ripgrep (rg) 可执行文件

## 2026-04-03 00:27:00 - winget 包检查
- winget search ripgrep 找到两个版本: BurntSushi.ripgrep.GNU (15.1.0) 和 BurntSushi.ripgrep.MSVC (15.1.0)
- rg 命令当前不在 PATH 中，无冲突的 rg 可执行文件
- 选择 MSVC 版本安装，Windows 兼容性最佳

## 2026-04-03 00:34:00 - 安装过程
- 网络代理问题导致首次安装失败 (InternetOpenUrl() failed)
- 加速器开启后网络恢复正常
- 成功通过 winget 安装 BurntSushi.ripgrep.MSVC 15.1.0
- winget 提示需要重启 shell 才能使 PATH 更改生效
- 备用方案：已下载 rg.exe 到临时目录并验证可用

## 2026-04-03 00:38:00 - PATH修复方案
- winget 修改了系统 PATH，但需要重启才能使更改生效
- 临时解决方案：将 rg.exe 复制到已在 PATH 中的目录 `C:\Users\Administrator\AppData\Local\Microsoft\WindowsApps\`
- 验证成功：glob 和 grep 工具现在正常工作
- 根本解决：重启系统或 OpenCode 会话后，winget 的 PATH 修改将自动生效