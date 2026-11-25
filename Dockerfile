# ─────────────────────────────────────────────────────────────────────────────
# configured_landers_linux — Dockerfile
#
# Fully self-contained:
# 1. Installs Google Chrome Stable + matching ChromeDriver in the image.
# 2. Can run with or without the 280MB setup/chrome-for-testing-149 folder.
# 3. Starts Xvfb virtual display on :99 for headless browser operation.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# ── Force IPv4 and retries for reliable apt downloads on Proxmox / VM networks
RUN echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4 \
    && echo 'Acquire::Retries "5";' >> /etc/apt/apt.conf.d/99force-ipv4 \
    && echo 'Acquire::http::Timeout "60";' >> /etc/apt/apt.conf.d/99force-ipv4 \
    && echo 'Acquire::https::Timeout "60";' >> /etc/apt/apt.conf.d/99force-ipv4

# ── OS-level dependencies + Xvfb ─────────────────────────────────────────────
RUN apt-get update && apt-get install -y --fix-missing --no-install-recommends \
    xvfb \
    curl \
    wget \
    unzip \
    gnupg \
    fonts-liberation \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-indic \
    fonts-dejavu-core \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    psmisc \
    procps \
    && rm -rf /var/lib/apt/lists/*


# ── Install Google Chrome Stable ─────────────────────────────────────────────
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y --fix-missing --no-install-recommends ./google-chrome-stable_current_amd64.deb \
    && rm -f ./google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# (ChromeDriver is no longer needed with Playwright)
# (ChromeDriver is no longer needed with Playwright)

WORKDIR /app

# ── Python dependencies ──────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy project files ───────────────────────────────────────────────────────
COPY . .

# ── Fix permissions if local Chrome bundle is present ───────────────────────
RUN if [ -d "setup/chrome-for-testing-149" ]; then \
    chmod -R +x setup/chrome-for-testing-149/ 2>/dev/null || true ; \
    fi

# ── Runtime directories ──────────────────────────────────────────────────────
RUN mkdir -p logs er_logs images zip getApi_data getApi_data_dev handoff_logs

# ── Script permissions ───────────────────────────────────────────────────────
RUN chmod +x start_process.sh stop_process.sh

# ── Optional per-image default network (set via --build-arg NETWORK=...) ────
ARG NETWORK=""
ENV NETWORK=${NETWORK}

# ── Expose Prometheus ports (one per instance, up to 50) ────────────────────
EXPOSE 8000-8049

# ── Entrypoint: start Xvfb then run new_lander.py ────────────────────────────
CMD ["bash", "-c", "Xvfb :99 -screen 0 1280x800x24 & sleep 1; export DISPLAY=:99; exec python3 -u new_lander.py"]