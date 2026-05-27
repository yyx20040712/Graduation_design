# ddesign_tool — 可重现构建环境
# 使用: docker build -t ddesign_tool . && docker run ddesign_tool validate --all

FROM python:3.11-slim

WORKDIR /app

# 安装构建依赖
RUN pip install --no-cache-dir pyinstaller

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ddesign_tool/ ddesign_tool/
COPY mods/ mods/
COPY output/ output/
COPY tests/ tests/
COPY pyproject.toml .
COPY config.ini .
COPY ddesign_tool.spec .

# 构建 EXE
RUN pyinstaller --clean --log-level=WARN ddesign_tool.spec

# 验证
RUN dist/ddesign_tool/ddesign_tool validate --all --ci

# 输出
CMD ["bash"]
