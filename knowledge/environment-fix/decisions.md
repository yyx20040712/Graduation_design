# 环境修复决策记录

## 2026-04-03 00:25:00 - 初步决策
1. **安装方法选择**：优先使用 winget 包管理器，因为它：
   - 已预装于系统 (v1.28.220)
   - 微软官方维护
   - 最小权限需求
   - 易于回滚

2. **安全优先原则**：
   - 不修改系统核心文件
   - 不删除现有文件
   - 使用用户空间安装方式

3. **验证策略**：
   - 安装后立即测试 `rg --version`
   - 验证 `glob` 和 `grep` 工具功能
   - 检查 PATH 配置是否自动更新

## 2026-04-03 00:30:00 - 安装执行决策
1. **版本选择**：安装 `BurntSushi.ripgrep.MSVC` (15.1.0) 而非 GNU 版本，因为：
   - MSVC 编译版在 Windows 上兼容性最佳
   - 静态链接 CRT，无需额外运行时
   - winget 包已修复 `rg` 别名冲突问题（PR #348127）

2. **安装命令**：
   ```
   winget install BurntSushi.ripgrep.MSVC --accept-package-agreements --accept-source-agreements
   ```
   - 使用完整包 ID 避免与其他 `rg` 软件包冲突
   - 接受协议以避免交互式提示

3. **风险评估**：
   - winget 安装仅添加新文件，不会删除现有文件
   - 安装位置在 `C:\Program Files\` 或用户空间，不影响系统核心
   - 如有问题可使用 `winget uninstall BurntSushi.ripgrep.MSVC` 完全卸载

## 2026-04-03 00:39:00 - PATH修复决策
1. **问题诊断**：winget 成功安装但 PATH 更新未立即生效（需要重启 shell）
2. **临时解决方案**：将 rg.exe 手动复制到已存在于 PATH 中的目录：
   - 目标目录：`C:\Users\Administrator\AppData\Local\Microsoft\WindowsApps\`
   - 理由：该目录已在系统 PATH 中，用户有写入权限，无需管理员权限
3. **验证结果**：
   - ✅ glob 工具现在正常工作（找到 9 个 txt 文件）
   - ✅ grep 工具不再报 "rg not found" 错误
   - ✅ rg --version 输出正常（15.1.0）
4. **长期解决方案**：
   - 重启系统或 OpenCode 会话后，winget 的 PATH 修改将自动生效
   - 届时可安全删除 WindowsApps 目录中的 rg.exe 副本