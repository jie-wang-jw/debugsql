# syntax=docker/dockerfile:1.7

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/
ENV UV_HTTP_TIMEOUT=600
ENV UV_HTTP_CONNECT_TIMEOUT=30
ENV UV_HTTP_RETRIES=5
ENV UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install uv

# Aliyun exposes PyTorch CPU wheels as a flat file directory rather than a
# PEP 503 package index, so install the pinned Linux wheels by URL. Keeping
# this in its own layer avoids downloading the 168 MB torch wheel whenever
# ordinary application dependencies change.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps \
    "https://mirrors.aliyun.com/pytorch-wheels/cpu/torch-2.7.1%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl" \
    "https://mirrors.aliyun.com/pytorch-wheels/cpu/torchvision-0.22.1%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl"

COPY pyproject.toml uv.lock requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
