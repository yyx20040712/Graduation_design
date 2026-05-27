# 毕业设计项目文档

## 项目概述
本项目为毕业设计项目，主要功能为管道计算和相关工程分析。

## 目录结构

### 核心应用程序
- **ddesign_tool/** - 排水管道设计工具主应用程序
  - `main.py` - 程序入口点
  - `src/` - 源代码目录（包含所有计算模块）
  - `data/` - 测试数据文件（Excel格式）
  - `config.ini` - 设计参数配置

### 核心模块（位于 ddesign_tool/src/）
- **calculate_pipes.py** - 管道水力计算主程序
- **design_engine.py** - 核心设计逻辑引擎
- **data_loader.py** - Excel数据加载与解析
- **result_writer.py** - 结果输出模块
- **pipe_calculation.py** - 管道计算工具类
- **stom_pipes.py** - 雨水管道计算
- **chuchenchi.py** - 初沉池计算
- **chenshachi.py** - 沉砂池计算
- **geshan.py** - 格栅计算

### 项目配置与文档
- **pyproject.toml** - 项目配置和依赖管理（现代Python标准）
- **requirements.txt** - Python核心依赖
- **requirements-dev.txt** - 开发工具依赖
- **docs/** - 项目文档（当前目录）
- **tests/** - 测试模块

## 使用指南

### 排水管道设计工具完整工作流

#### 1. 准备输入数据
- 将Excel数据文件放入 `ddesign_tool/data/` 目录
- Excel文件格式要求：
  - 每个工作表代表一个设计案例
  - 每行数据包含8列：起点编号, 终点编号, 长度(m), 起点地面标高(m), 终点地面标高(m), 本段汇水面积(ha), 本段产生流量(L/s), 污水提升(m)
  - 第一行为标题行

#### 2. 配置设计参数
- 编辑 `ddesign_tool/config.ini` 文件调整设计参数：
  - 曼宁粗糙系数 (`manning_n`)
  - 流速限制 (`min_velocity`, `max_velocity`)
  - 最小设计坡度 (`default_min_slope`)
  - 管道类型 (`pipe_type`)

#### 3. 运行设计计算
```bash
# 从项目根目录运行
python ddesign_tool/main.py

# 或直接指定数据文件
python ddesign_tool/main.py ddesign_tool/data/pipe_final.xlsx
```

#### 4. 查看和验证结果
- 计算结果保存到原Excel文件的"计算结果"工作表
- 管道统计信息保存到"管道统计"工作表
- 详细日志保存在 `ddesign_tool/logs/` 目录
- 输出文件保存在 `ddesign_tool/output/` 目录

### 专业计算模块功能

#### 管道水力计算模块
- 基于曼宁公式的管道水力计算
- 自动管径选择和坡度优化
- 并联管道设计支持
- 高程计算和跌水井设计

#### 专业处理设施计算
- **雨水管道计算** (`stom_pipes.py`) - 暴雨强度公式应用
- **初沉池计算** (`chuchenchi.py`) - 沉淀池尺寸设计
- **沉砂池计算** (`chenshachi.py`) - 沉砂池水力计算
- **格栅计算** (`geshan.py`) - 格栅尺寸和数量计算

## API参考

### 排水管道设计工具模块

#### 导入和使用核心设计引擎
```python
# 方式1：从ddesign_tool目录运行时的导入
from src.design_engine import DrainagePipeDesigner

# 创建设计器实例
designer = DrainagePipeDesigner(manning_n=0.014)

# 执行管道设计
pipe_design = designer.design_pipe(
    flow_rate=50.0,    # 流量(L/s)
    pipe_length=100.0,  # 管道长度(m)
    ground_slope=0.005  # 地面坡度
)
```

#### 数据加载模块
```python
from src.data_loader import read_pipe_data

# 读取Excel管道数据
pipes = read_pipe_data("data/pipe_final.xlsx")

# 返回数据结构：List[Dict]，包含管道基本参数
```

#### 结果输出模块
```python
from src.result_writer import write_results

# 将设计结果写入Excel
write_results(
    excel_path="output/result.xlsx",
    pipes=pipes_data,
    designs=design_results,
    elevations=elevation_data
)
```

### 专业计算模块
```python
# 雨水管道计算
from src.stom_pipes import calculate_stormwater

# 初沉池计算
from src.chuchenchi import calculate_primary_settling

# 沉砂池计算
from src.chenshachi import calculate_grit_chamber

# 格栅计算
from src.geshan import calculate_bar_screen
```

## 开发指南

### 项目结构规范
- **主应用程序**: `ddesign_tool/` 目录包含完整的排水设计工具
- **源代码组织**: `ddesign_tool/src/` 目录按功能模块组织
- **数据管理**: `ddesign_tool/data/` 存放测试数据，`output/` 存放结果
- **配置分离**: `config.ini` 管理设计参数，与代码逻辑分离

### 代码规范
- 严格遵循 PEP 8 编码规范
- 使用类型提示（Type Hints）增强代码可读性
- 所有公共函数和类必须包含完整的文档字符串（docstrings）
- 使用 Black 进行代码格式化，isort 进行导入排序

### 测试规范
- 单元测试放在 `tests/` 目录，与源代码分离
- 测试文件命名：`test_*.py`，测试类命名：`Test*`
- 使用 pytest 框架，支持参数化测试和夹具
- 目标测试覆盖率：80%+（使用 pytest-cov 监测）

### 开发工作流
1. **环境设置**: 使用项目级虚拟环境（`.venv/`）
2. **依赖管理**: 通过 `pyproject.toml` 或 `requirements.txt`
3. **代码质量**: 提交前运行 `pre-commit` 钩子检查
4. **提交规范**: 遵循约定式提交（Conventional Commits）
5. **版本控制**: 功能分支工作流，定期合并到主分支

## 故障排除

### 常见问题与解决方案

#### 1. 依赖安装问题
**问题**: 无法安装项目依赖
```bash
# 解决方案1：确保使用正确的Python版本（3.10+）
python --version

# 解决方案2：使用项目根目录的requirements.txt
pip install -r requirements.txt

# 解决方案3：清理缓存后重试
pip cache purge
pip install --no-cache-dir -r requirements.txt
```

#### 2. 模块导入错误
**问题**: `ModuleNotFoundError` 或导入路径错误
```bash
# 确保在正确的目录运行
# 从项目根目录运行：
python ddesign_tool/main.py

# 或从ddesign_tool目录运行：
cd ddesign_tool
python main.py
```

#### 3. Excel文件读取错误
**问题**: 无法读取Excel数据文件
- 确保Excel文件在 `ddesign_tool/data/` 目录中
- 检查Excel文件格式是否符合要求（8列数据）
- 确认文件未被其他程序占用

#### 4. 设计计算错误
**问题**: 设计结果异常或程序崩溃
- 检查 `config.ini` 中的设计参数是否合理
- 验证输入数据单位是否正确
- 查看 `logs/` 目录中的详细错误日志

#### 5. 代码质量检查失败
```bash
# 自动修复格式问题
black .
isort .

# 检查代码风格
flake8 ddesign_tool/src/

# 类型检查
mypy ddesign_tool/src/
```

## 扩展开发

### 添加新的设计模块
1. **模块创建**: 在 `ddesign_tool/src/` 目录创建新模块文件（如 `new_module.py`）
2. **功能实现**: 实现核心计算逻辑，遵循现有设计模式
3. **接口设计**: 提供清晰的函数接口和类型提示
4. **测试编写**: 在 `tests/` 目录添加对应的单元测试
5. **文档更新**: 更新本文档和模块的docstrings
6. **集成测试**: 验证与现有模块的兼容性

### 修改现有设计逻辑
- **设计引擎**: 修改 `design_engine.py` 中的核心算法
- **数据加载**: 调整 `data_loader.py` 支持新数据格式
- **结果输出**: 扩展 `result_writer.py` 的输出格式
- **配置管理**: 在 `config.ini` 中添加新参数支持

### 性能优化策略
- **向量化计算**: 使用numpy替代Python循环进行数值计算
- **缓存机制**: 对耗时的计算结果实现缓存
- **并行处理**: 对独立计算任务实现多线程/多进程
- **内存优化**: 处理大型数据集时使用分块读取

### 代码重构建议
- **模块拆分**: 当单个模块过大时，按功能拆分为子模块
- **接口统一**: 确保相似功能的模块提供一致的API
- **错误处理**: 增强错误处理和异常捕获机制
- **日志优化**: 提供更详细的调试和运行日志

---
*文档最后更新：2026年4月13日（项目结构整理后）*  
*原始创建：2026年4月3日*

**维护说明**: 本项目已按现代Python最佳实践进行结构整理，建议后续开发遵循相同规范。