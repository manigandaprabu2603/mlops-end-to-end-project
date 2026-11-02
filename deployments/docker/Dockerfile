FROM python:3.10-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=10001:10001 model/ /app/model/
USER 10001:10001
EXPOSE 8080
CMD ["mlflow", "models", "serve", "--model-uri", "/app/model", "--host", "0.0.0.0", "--port", "8080", "--env-manager", "local", "--workers", "1"]
