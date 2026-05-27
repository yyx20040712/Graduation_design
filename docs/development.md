# 开发环境配置指南

## 目录
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [虚拟环境管理](#虚拟环境管理)
- [依赖管理](#依赖管理)
- [代码质量检查](#代码质量检查)
- [测试](#测试)
- [代码提交规范](#代码提交规范)
- [开发工作流](#开发工作流)

## 环境要求

### 系统要求
- **操作系统**: Windows 10/11, macOS 10.15+, 或 Linux
- **Python版本**: 3.10 或更高版本 (推荐 3.10+)
- **内存**: 至少 4GB RAM
- **磁盘空间**: 至少 2GB 可用空间

### 必需工具
1. **Python 3.10+**: [下载地址](https://www.python.org/downloads/)
2. **Git**: [下载地址](https://git-scm.com/downloads)
3. **代码编辑器** (推荐):
   - VS Code: [下载地址](https://code.visualstudio.com/)
   - PyCharm: [下载地址](https://www.jetbrains.com/pycharm/)

## 快速开始

### 1. 克隆项目
```bash
git clone <项目仓库地址>
cd Graduation_design
```

### 2. 设置虚拟环境
```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate
```

### 3. 安装依赖
```bash
# 方式1: 使用 requirements.txt (传统方式)
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发依赖

# 方式2: 使用 pyproject.toml (现代方式)
pip install .          # 安装核心依赖
pip install .[dev]     # 安装开发依赖
```

### 4. 验证安装
```bash
# 运行简单测试
pytest tests/test_sample.py -v

# 检查Python环境
python --version
pip list
```

## 虚拟环境管理

### 创建虚拟环境
```bash
python -m venv .venv
```

### 激活虚拟环境
```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 停用虚拟环境
```bash
deactivate
```

### 删除虚拟环境
```bash
# 直接删除 .venv 目录
rm -rf .venv  # Linux/Mac
rmdir /s .venv  # Windows
```

## 依赖管理

### 项目依赖文件
- **`pyproject.toml`**: 项目配置和依赖声明 (现代Python标准)
- **`requirements.txt`**: 核心依赖列表 (兼容传统方式)
- **`requirements-dev.txt`**: 开发依赖 (测试、代码质量、文档工具)

### 安装依赖
```bash
# 安装所有依赖 (推荐方式)
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 或使用 pyproject.toml
pip install .[dev]
```

### 更新依赖
```bash
# 更新 requirements.txt
pip freeze > requirements.txt

# 添加新依赖
pip install <包名>
pip freeze > requirements.txt  # 更新文件
```

### 依赖版本管理
- 生产环境: 使用固定版本 (`包名==版本号`)
- 开发环境: 使用兼容版本 (`包名>=版本号`)

## 代码质量检查

### 预提交钩子 (Pre-commit)
项目配置了Git预提交钩子，自动检查代码质量。

```bash
# 安装预提交钩子
pre-commit install

# 手动运行所有检查
pre-commit run --all-files

# 跳过预提交检查 (不推荐)
git commit --no-verify
```

### 代码格式化
```bash
# 使用 Black 格式化代码
black .

# 使用 isort 排序导入
isort .

# 自动修复所有格式问题
black . && isort .
```

### 代码风格检查
```bash
# 使用 flake8 检查代码风格
flake8 .

# 检查特定文件
flake8 code/calculate_pipes.py

# 显示详细错误
flake8 . --statistics
```

### 类型检查
```bash
# 使用 mypy 进行类型检查
mypy .
```

## 测试

### 运行测试
```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_sample.py

# 运行测试并显示详细输出
pytest -v

# 运行测试并生成覆盖率报告
pytest --cov=.
```

### 测试覆盖率
```bash
# 生成HTML覆盖率报告
pytest --cov=. --cov-report=html

# 查看控制台覆盖率报告
pytest --cov=. --cov-report=term-missing
```

### 测试策略
1. **单元测试**: 测试单个函数或类
2. **集成测试**: 测试模块间的交互
3. **功能测试**: 测试完整的功能流程

## 代码提交规范

### 提交信息格式
```
类型(范围): 简要描述

详细描述（可选）

BREAKING CHANGE: 重大变更说明（可选）
```

### 提交类型
- `feat`: 新功能
- `fix`: 错误修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具变动

### 示例
```
feat(pipe-calculation): 添加管道水力计算功能

- 实现曼宁公式计算
- 添加管道尺寸选择算法
- 添加单元测试

BREAKING CHANGE: 修改了code/calculate_pipes.py的API接口
```

## 开发工作流

### 1. 创建功能分支
```bash
git checkout -b feature/功能名称
```

### 2. 开发代码
- 编写功能代码
- 添加单元测试
- 运行测试确保通过

### 3. 代码质量检查
```bash
# 运行预提交检查
pre-commit run --all-files

# 运行测试
pytest

# 修复所有问题
black . && isort . && flake8 .
```

### 4. 提交代码
```bash
git add .
git commit -m "feat(scope): 描述变更"
```

### 5. 推送分支
```bash
git push origin feature/功能名称
```

### 6. 创建Pull Request
- 在GitHub/GitLab上创建Pull Request
- 等待代码审查
- 通过CI/CD检查

## 故障排除

### 常见问题

#### 1. 导入错误
```python
# 错误: ModuleNotFoundError: No module named 'numpy'
# 解决方案: 安装缺失的依赖
pip install numpy
```

#### 2. 虚拟环境问题
```bash
# 错误: 'venv'不是内部或外部命令
# 解决方案: 使用完整路径
python -m venv .venv
```

#### 3. 预提交钩子失败
```bash
# 错误: pre-commit钩子检查失败
# 解决方案: 修复代码问题或跳过检查
pre-commit run --all-files  # 查看具体错误
git commit --no-verify      # 跳过检查 (不推荐)
```

#### 4. 测试失败
```bash
# 错误: 测试用例失败
# 解决方案: 修复测试或代码
pytest -v  # 查看详细错误信息
```

### 获取帮助
1. 查看项目文档: `docs/` 目录
2. 检查错误日志
3. 搜索相关错误信息
4. 咨询指导老师

---
*最后更新: 2026年4月13日（项目结构整理后）*  
*原始创建: 2026年4月3日*

**维护说明**: 本开发指南适用于整理后的项目结构，已移除过时信息，保持最佳实践推荐。