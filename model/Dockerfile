FROM python:3.10-slim

WORKDIR /app

# libgomp1 = OpenMP runtime required by LightGBM (libgomp.so.1). Without it,
# `import lightgbm` fails with OSError and training never runs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# Pin MLflow to the tracking server's version (ghcr.io/mlflow/mlflow:v2.17.2).
# mlflow>=2.17.0 now resolves to 3.x, whose client calls /api/2.0/mlflow/logged-models
# which the 2.17 server doesn't have → 404 on log_model.
RUN pip install --no-cache-dir -r requirements.txt mlflow==2.17.2

COPY train.py ./
COPY artifacts/ ./artifacts/

ENV PYTHONUNBUFFERED=1

CMD ["python", "train.py"]
