# Object-storage (MinIO) cutover — AIPPT prod

The `data` volume is now an ephemeral read-through/write-through **cache**.
The durable source of truth is MinIO at `s3minio.amd.com:21000`, bucket
`ogmatic-zoo`, prefix `asic/aippt/`. The deployment turns this on via
`AIPPT_STORAGE=s3` (see `deployment.yaml`).

## One-time setup

### 1. Mint a MinIO access key (scoped to `asic/`)

In the MinIO console (`https://s3minio.amd.com:21001`, LDAP login) create an
access key for AIPPT. It only needs read/write under `asic/`.

### 2. Add the credentials to the sealed Secret

The keys live in `aippt-secrets` alongside `AMD_LLM_KEY`. Edit the SOPS-encrypted
file with your age key (do **not** commit plaintext):

```bash
cd deploy/slai-app-prod/aippt
sops secrets.enc.yaml      # adds entries under stringData:
#   MINIO_ACCESS_KEY: <key>
#   MINIO_SECRET_KEY: <secret>
```

`deployment.yaml` already wires both into the container via `secretKeyRef`.

### 3. Seed MinIO from current local data (optional, for cutover)

If the running pod (or a local checkout) holds decks/images worth keeping,
back them up before cutover. From an environment with the data dir and
`MINIO_*` env set:

```bash
export AIPPT_STORAGE=s3 MINIO_ENDPOINT=s3minio.amd.com:21000 \
       MINIO_BUCKET=ogmatic-zoo MINIO_PREFIX=asic/aippt/ \
       MINIO_ACCESS_KEY=… MINIO_SECRET_KEY=… \
       MINIO_CA_BUNDLE=/etc/ssl/certs/ca-bundle-with-amd.pem
python aippt.py storage backfill --data-dir /app/data --dry-run   # preview
python aippt.py storage backfill --data-dir /app/data             # upload
```

This uploads `uploads/`, `images/`, `output/` and snapshots the catalog to
`catalog/slides.db`. `backups/` and the `$HOME` cache stay node-local.

## TLS trust

The image bakes the AMD Corporate Root CA + `AMD-com Issuing CA` (from
`deploy/ca/amd-root-ca.pem`) into `/etc/ssl/certs/ca-bundle-with-amd.pem`;
`MINIO_CA_BUNDLE` points minio-py at it so verification works under
`readOnlyRootFilesystem`. If MinIO's cert is ever reissued under a different
chain, update `deploy/ca/amd-root-ca.pem` and rebuild.

## Runtime behavior

- **Startup:** the catalog is restored from `catalog/slides.db` into
  `/app/data/slides.db` before the server opens it (empty start if absent).
- **Writes:** decks, images, sources, and output are uploaded after they are
  produced; catalog mutations trigger a debounced snapshot (single-writer —
  keep `replicas: 1`).
- **Reads:** a cold pod fetches each asset from MinIO into the local cache on
  first request (`/slide-image`, download, regenerate, write-notes).

## Rollback

Set `AIPPT_STORAGE=fs` (or remove the var) and redeploy. The app reverts to the
local `data` volume; no object-storage calls are made.
