# Workstation container that simulates employee browsing
# This will trigger BeEF hooks when attacker injects XSS
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    firefox \
    python3 \
    python3-pip \
    xvfb \
    wget \
    iproute2 \
    iputils-ping \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Selenium
RUN pip3 install selenium

# Install geckodriver
RUN wget -q https://github.com/mozilla/geckodriver/releases/download/v0.33.0/geckodriver-v0.33.0-linux64.tar.gz && \
    tar -xzf geckodriver-v0.33.0-linux64.tar.gz && \
    mv geckodriver /usr/local/bin/ && \
    rm geckodriver-v0.33.0-linux64.tar.gz

COPY browse-script.py /browse-script.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /browse-script.py

ENTRYPOINT ["/entrypoint.sh"]
