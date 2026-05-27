"""示例测试文件,展示如何为毕业设计项目编写测试."""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path


def test_import_project_modules():
    """测试是否可以导入项目模块."""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ddesign_tool", "src"))
        from models.base import WaterFlow, WaterQuality
        assert True
    except ImportError as e:
        pytest.fail(f"无法导入项目模块: {e}")


def test_basic_math():
    """测试基本数学运算."""
    result = 2 + 3
    assert result == 5, f"2+3应该等于5,但得到{result}"


def test_numpy_available():
    """测试NumPy是否正确安装."""
    arr = np.array([1, 2, 3])
    assert len(arr) == 3
    assert arr.sum() == 6


def test_pandas_available():
    """测试Pandas是否正确安装."""
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    assert df.shape == (3, 2)
    assert df["A"].sum() == 6


def test_project_structure():
    """测试项目目录结构."""
    project_path = Path(__file__).parent.parent
    
    # 检查关键文件是否存在
    required_files = [
        "README.md",
        "pyproject.toml",
        "requirements.txt",
        ".gitignore",
        "ddesign_tool/main.py",
    ]
    
    for file_name in required_files:
        file_path = project_path / file_name
        assert file_path.exists(), f"缺少文件: {file_name}"
    
    # 检查ddesign_tool目录是否存在
    excel_dir = project_path / "ddesign_tool"
    assert excel_dir.exists(), "缺少ddesign_tool目录"


def test_excel_files():
    """测试Excel文件读取(如果存在)."""
    project_path = Path(__file__).parent.parent
    excel_dir = project_path / "excel"
    
    if excel_dir.exists():
        # 检查是否有Excel文件
        excel_files = list(excel_dir.glob("*.xlsx")) + list(excel_dir.glob("*.xls"))
        if excel_files:
            # 测试第一个Excel文件是否可以读取
            try:
                test_file = excel_files[0]
                df = pd.read_excel(test_file, sheet_name=None, nrows=5)  # 只读前5行测试
                assert df is not None
            except Exception as e:
                pytest.skip(f"无法读取Excel文件 {test_file}: {e}")
        else:
            pytest.skip("excel目录中没有Excel文件")
    else:
        pytest.skip("excel目录不存在")


class TestPipeCalculation:
    """管道计算相关测试."""
    
    def test_manning_formula(self):
        """测试曼宁公式基本计算."""
        # 曼宁公式: V = (1/n) * R^(2/3) * S^(1/2)
        n = 0.014  # 曼宁系数
        R = 0.5    # 水力半径
        S = 0.001  # 坡度
        
        V = (1 / n) * (R ** (2/3)) * (S ** (1/2))
        
        # 验证计算结果合理
        assert V > 0, "流速应为正值"
        assert isinstance(V, float), "流速应为浮点数"
    
    def test_pipe_area(self):
        """测试管道截面积计算."""
        diameter = 0.5  # 管径0.5米
        expected_area = np.pi * (diameter / 2) ** 2
        calculated_area = np.pi * (0.25) ** 2
        
        assert abs(expected_area - calculated_area) < 1e-10


def test_environment_variables():
    """测试环境变量(如果有)."""
    import os
    
    # 检查是否设置了Python路径
    python_path = os.environ.get("PYTHONPATH", "")
    assert isinstance(python_path, str)


# 参数化测试示例
@pytest.mark.parametrize("input_val,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
    (0, 0),
])
def test_double_function(input_val, expected):
    """测试简单的双倍函数."""
    result = input_val * 2
    assert result == expected, f"{input_val}*2应该等于{expected},但得到{result}"


if __name__ == "__main__":
    # 直接运行测试
    pytest.main([__file__, "-v"])