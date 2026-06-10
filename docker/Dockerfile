# DerivKit Harbor/QFbench-compatible runtime image
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    OMP_NUM_THREADS=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY docker/requirements-harbor.txt ./docker/requirements-harbor.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r docker/requirements-harbor.txt \
    && pip install --no-cache-dir .

RUN mkdir -p /app/output

VOLUME ["/app/output"]

ENTRYPOINT ["python", "-m", "derivkit.integ.sandbox_runner"]
