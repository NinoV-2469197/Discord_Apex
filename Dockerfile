# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS runtime

ARG APP_DIR=apex

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_DIR=${APP_DIR}

WORKDIR /bot

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg62-turbo-dev \
        libopenjp2-7 \
        zlib1g-dev \
        libtiff6 \
        libwebp-dev \
        liblcms2-2 \
    && rm -rf /var/lib/apt/lists/*

COPY ${APP_DIR}/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY ${APP_DIR}/ /bot/

CMD ["python", "main.py"]

