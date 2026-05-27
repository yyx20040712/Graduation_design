# 排水管道设计工具 (Drainage Design Tool)

## 项目概述

本软件为毕业设计项目开发的排水管道水力设计工具，基于曼宁公式与GB50014-2021规范。主要功能包括管道水力计算、高程设计、结果输出等。

## 主要特性

- **规范遵循**: 严格遵循GB50014-2021《室外排水设计标准》
- **智能设计**: 支持并联管道设计，自动优化管径和坡度
- **灵活配置**: 可通过配置文件调整设计参数
- **多种接口**: 支持GUI文件选择对话框和命令行输入
- **完整输出**: 生成详细计算结果和统计报表

## 项目结构

```
ddesign_tool/
│
├── data/                     # 测试输入数据（Excel文件）
│   ├── pipe_final.xlsx       # 管道计算测试数据
│   ├── pipe_final2.xlsx      # 管道计算测试数据2
│   ├── yushui.xlsx           # 雨水管道数据
│   ├── chuchenchi.xlsx       # 初沉池数据
│   ├── chenshachi.xlsx       # 沉砂池数据
│   └── geshan.xlsx           # 格栅数据
│
├── src/                      # 源代码目录
│   ├── __init__.py           # Python包初始化
│   ├── data_loader.py        # 模块1：数据输入与解析
│   ├── design_engine.py      # 模块2：核心设计逻辑
│   ├── task_manager.py       # 模块3：任务管理与调度
│   ├── result_writer.py      # 模块4：结果输出
│   ├── cli.py                # 模块5：命令行界面
│   ├── calculate_pipes.py    # 管道水力计算主模块
│   ├── pipe_calculation.py   # 管道计算工具类
│   ├── stom_pipes.py         # 雨水管道计算模块
│   ├── chuchenchi.py         # 初沉池计算模块
│   ├── chenshachi.py         # 沉砂池计算模块
│   └── geshan.py             # 格栅计算模块
│
├── main.py                   # 程序入口（调用cli或直接串联模块）
├── config.ini                # 配置文件（设计参数、路径等）
├── requirements.txt          # 工具特定依赖库列表
└── README.md                 # 软件说明（当前文件）
```

*注：output/和logs/目录在程序首次运行时自动创建*

## 快速开始

### 1. 环境配置

```bash
# 方式A：从ddesign_tool目录安装（工具特定依赖）
cd ddesign_tool
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装工具依赖
pip install -r requirements.txt

# 方式B：从项目根目录安装（推荐，包含完整项目依赖）
# 在项目根目录（Graduation_design/）执行：
# pip install -r requirements.txt
# 或使用现代方式：pip install .[dev]
```

### 2. 准备数据文件

1. 将Excel数据文件放入 `data/` 目录
2. Excel文件格式要求：
   - 每个工作表代表一个设计案例
   - 每行数据包含8列：起点编号, 终点编号, 长度(m), 起点地面标高(m), 终点地面标高(m), 本段汇水面积(ha), 本段产生流量(L/s), 污水提升(m)
   - 第一行为标题行

### 3. 运行程序

```bash
# 运行主程序（会弹出文件选择对话框）
python main.py

# 或直接指定文件路径
python main.py data/your_data.xlsx
```

### 4. 查看结果

- 计算结果保存在原Excel文件的"计算结果"工作表中
- 管道统计信息保存在"管道统计"工作表中
- 程序运行日志保存在 `logs/` 目录

## 模块说明

### 1. data_loader.py
- 功能：读取Excel数据文件，解析管道数据
- 输入：Excel文件路径
- 输出：管道数据列表，上下游关系映射

### 2. design_engine.py
- 功能：核心水力设计计算
- 核心类：`DrainagePipeDesigner`
- 基于曼宁公式，考虑规范约束（充满度、流速、坡度）

### 3. task_manager.py
- 功能：管道设计任务管理
- 包括单管道设计 (`design_pipe`) 和高程计算 (`process_pipe`)

### 4. result_writer.py
- 功能：结果输出到Excel
- 生成详细设计报表和统计信息

### 5. cli.py
- 功能：命令行界面
- 处理用户输入，协调各模块工作流

## 配置说明

通过 `config.ini` 文件可以调整设计参数：

- `design_parameters`: 设计参数（曼宁系数、流速限制等）
- `paths`: 路径配置（数据目录、输出目录等）
- `logging`: 日志配置

## 依赖库

主要依赖：
- pandas: 数据处理
- openpyxl: Excel文件读写
- numpy: 数值计算
- (可选) tkinter: GUI文件选择对话框

完整依赖列表见 `requirements.txt`

## 开发说明

### 代码规范
- 遵循 PEP 8 代码风格
- 使用类型提示 (Type Hints)
- 重要函数添加文档字符串

### 测试
```bash
# 运行测试
pytest tests/

# 代码质量检查
flake8 src/
```

### 扩展开发
1. 添加新的设计模块：在 `src/` 目录下创建新模块
2. 修改设计逻辑：编辑 `design_engine.py`
3. 调整输出格式：修改 `result_writer.py`

## 注意事项

1. 本软件为毕业设计作品，实际工程应用请结合具体规范复核
2. 确保输入数据格式正确，特别是单位统一
3. 设计结果仅供参考，重要工程需专业复核

## 许可证

MIT License

## 联系信息

如有问题或建议，请联系项目维护者。

---
**版本**: 1.0.0  
**项目整理日期**: 2026-04-13  
**原始创建日期**: 2026-04-03

*注：本项目结构已按现代Python最佳实践进行整理，移除重复文件，统一文档描述*