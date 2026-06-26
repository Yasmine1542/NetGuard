# NetGuard inference service.
#
# IMPORTANT: build with the demo-app/ directory as the build context (NOT
# services/inference/), so the model artifacts can be baked into the image:
#     docker build -f services/inference/Dockerfile -t netguard-inference .
# Run that from demo-app/. The model becomes an immutable part of the image —
# a new model version = a new image tag, which is what the canary rolls out.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INFERENCE_MODEL_DIR=/models

# Pull the latest security patches, then install libgomp1 (LightGBM's OpenMP dep).
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/inference/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/inference/app ./app
# Bake the LightGBM artifacts (model.pkl, encoders.pkl, *.json) into the image.
COPY model/artifacts /models

# Run as an unprivileged user.
RUN useradd --system --no-create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
