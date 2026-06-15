FROM python:3.11-slim

# pdftoppm (from poppler-utils) is required by the SharePoint render pipeline:
# PPTX -> Graph -> PDF -> pdftoppm -> PNGs. See aippt/render.py.
# ca-certificates provides the base trust store we extend with the AMD root.
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Bake the AMD Corporate PKI chain into a combined CA bundle so minio-py can
# verify the s3minio.amd.com cert under readOnlyRootFilesystem. The manifest
# points MINIO_CA_BUNDLE at this file. These are public CA certs, not secrets.
COPY deploy/ca/amd-root-ca.pem /usr/local/share/ca-certificates-extra/amd-root-ca.pem
RUN cat /etc/ssl/certs/ca-certificates.crt \
        /usr/local/share/ca-certificates-extra/amd-root-ca.pem \
        > /etc/ssl/certs/ca-bundle-with-amd.pem

WORKDIR /app

# Install dependencies. On AMD-network build hosts, egress to pypi is
# TLS-intercepted by the AMD Corporate Root CA; pip verifies against its own
# bundled certifi store (not the system trust), so point it at the combined
# bundle baked above (public roots + AMD Corporate Root + issuing CA).
COPY requirements.txt .
RUN PIP_CERT=/etc/ssl/certs/ca-bundle-with-amd.pem pip install --no-cache-dir -r requirements.txt

# Copy application code (world-readable; ownership enforced by K8s securityContext)
COPY aippt/ aippt/
COPY aippt.py .
COPY pyproject.toml .
COPY dirs.yaml .
COPY gateway.yaml gateway.yaml
COPY models.yaml models.yaml
COPY templates.yaml templates.yaml

# Create data directory for SQLite, uploads, and images (writable via fsGroup)
RUN mkdir -p /app/data/uploads /app/data/images /app/data/backups && \
    chmod -R 0755 /app/data

EXPOSE 8000

ENTRYPOINT ["python", "aippt.py", "serve", "--host", "0.0.0.0", "--port", "8000", "--db", "/app/data/slides.db", "--uploads-dir", "/app/data/uploads", "--images-dir", "/app/data/images", "--data-dir", "/app/data"]
