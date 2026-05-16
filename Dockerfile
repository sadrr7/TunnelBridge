FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install GOST v3
RUN ARCH=$(dpkg --print-architecture) && \
    wget -q "https://github.com/go-gost/gost/releases/download/v3.0.0/gost_3.0.0_linux_${ARCH}.tar.gz" -O /tmp/gost.tar.gz && \
    tar -xzf /tmp/gost.tar.gz -C /tmp && \
    mv /tmp/gost /usr/local/bin/gost && chmod +x /usr/local/bin/gost && \
    rm /tmp/gost.tar.gz

# Install Xray-core
RUN wget -q "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip" -O /tmp/xray.zip && \
    unzip -q /tmp/xray.zip -d /tmp/xray && \
    mv /tmp/xray/xray /usr/local/bin/xray && chmod +x /usr/local/bin/xray && \
    rm -rf /tmp/xray /tmp/xray.zip

# Install Rathole
RUN wget -q "https://github.com/rapiz1/rathole/releases/latest/download/rathole-x86_64-unknown-linux-gnu.zip" -O /tmp/rathole.zip && \
    unzip -q /tmp/rathole.zip -d /tmp/rathole && \
    mv /tmp/rathole/rathole /usr/local/bin/rathole && chmod +x /usr/local/bin/rathole && \
    rm -rf /tmp/rathole /tmp/rathole.zip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
