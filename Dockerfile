FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN  pip install --trusted-host binarios.intranet.bb.com.br --trusted-host files.pythonhosted.org \
    --index-url=https://binarios.intranet.bb.com.br/artifactory/api/pypi/pypi/simple --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn","--bind","0.0.0.0:5000","app:app"]
