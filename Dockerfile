FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (world-readable; ownership enforced by K8s securityContext)
COPY aippt/ aippt/
COPY aippt.py .
COPY pyproject.toml .
COPY dirs.yaml .
COPY gateway.yaml gateway.yaml

# Create data directory for SQLite, uploads, and images (writable via fsGroup)
RUN mkdir -p /app/data/uploads /app/data/images /app/data/backups && \
    chmod -R 0755 /app/data

EXPOSE 8000

ENTRYPOINT ["python", "aippt.py", "serve", "--host", "0.0.0.0", "--port", "8000", "--db", "/app/data/slides.db", "--uploads-dir", "/app/data/uploads"]
