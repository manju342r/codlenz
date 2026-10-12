FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    OLLAMA_MODELS=/home/user/.ollama/models \
    CODELENS_HOST=0.0.0.0 \
    CODELENS_PORT=7860 \
    CORS_ORIGIN=*

# Install system utilities, Git, and Ollama
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    procps \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

# Non-root user required by Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user && \
    mkdir -p /home/user/.ollama && \
    mkdir -p /home/user/app && \
    chown -R user:user /home/user

WORKDIR /home/user/app

# Copy application files
COPY --chown=user:user . /home/user/app

RUN chmod +x /home/user/app/entrypoint.sh

USER user

# Install Python dependencies and package
RUN pip install --no-cache-dir --user -e .

EXPOSE 7860

CMD ["bash", "/home/user/app/entrypoint.sh"]
