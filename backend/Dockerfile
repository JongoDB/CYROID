# backend/Dockerfile
FROM python:3.11-slim

# Version passed from CI build (from root VERSION file)
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    p7zip-full \
    genisoimage \
    iptables \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "cyroid.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
