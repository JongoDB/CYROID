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
    curl \
    && rm -rf /var/lib/apt/lists/* \
    # Install Docker CLI for subprocess-based image transfers
    && curl -fsSL https://download.docker.com/linux/static/stable/$(uname -m)/docker-27.4.1.tgz | tar xz -C /usr/local/bin --strip-components=1 docker/docker

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "cyroid.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
