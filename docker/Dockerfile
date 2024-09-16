# 使用 Python 3.9 作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件到容器中
COPY .. /app

# 安装项目依赖
RUN pip install --upgrade pip && pip install -r requirements.txt

# 创建日志文件夹
RUN mkdir -p /app/log

# 运行 Flask 应用，日志输出到 log/flask.log
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--access-logfile", "/app/log/flask.log", "app:app"]
