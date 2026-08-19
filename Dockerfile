FROM python:3.10-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Bangkok
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg libopus0 tzdata build-essential libbz2-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir zeroc-ice==3.7.11 \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/static/records

EXPOSE 5000
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
