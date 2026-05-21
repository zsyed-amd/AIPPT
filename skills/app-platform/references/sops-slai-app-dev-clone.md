# SOPS + `.sops.yaml` when your app is **not** the `slai-app-dev` checkout

**Canonical path:** follow the steps below (markdown). **Optional:** on **Linux amd64**, **[`../scripts/encrypt-secrets-yaml.sh`](../scripts/encrypt-secrets-yaml.sh)** automates clone, **`chmod 700`**, and **`sops`** download -- use it only when it fits your environment.

**Do not assume** `AMD-SLAI/slai-app-dev` exists next to the application repository. The **public age recipient** and **creation rules** live in the platform repo root **`.sops.yaml`** only.

## Default: shallow clone under `/tmp/$USER`

Agents and developers should use a **dedicated clone** of the platform repo, typically:

| | |
|--|--|
| **Directory** | `/tmp/$USER/slai-app-dev` (Unix: `$USER` is the login name; substitute on other OS, or set **`SLAI_APP_DEV_DIR`** below). |
| **Purpose** | Read **`.sops.yaml`**, optionally validate manifests with **`skills/app-platform/scripts/main.py`**, and run **`sops`** with the correct config. |
| **Permissions** | After clone, set **`chmod 700`** on **`SLAI_APP_DEV_DIR`** so other users on the host cannot traverse or read the tree (reduces exposure if plaintext or keys are ever written under this path). |

**One-time (or refresh) clone:**

```bash
SLAI_APP_DEV_DIR="${SLAI_APP_DEV_DIR:-/tmp/${USER:-user}/slai-app-dev}"
mkdir -p "$(dirname "$SLAI_APP_DEV_DIR")"
if [[ ! -d "$SLAI_APP_DEV_DIR/.git" ]]; then
  git clone --depth 1 https://github.com/AMD-SLAI/slai-app-dev.git "$SLAI_APP_DEV_DIR"
else
  git -C "$SLAI_APP_DEV_DIR" pull --ff-only
fi
chmod 700 "$SLAI_APP_DEV_DIR"
```

Override the path when needed (CI, Windows, shared hosts). After the first clone (or when creating the directory), still run **`chmod 700 "$SLAI_APP_DEV_DIR"`**:

```bash
export SLAI_APP_DEV_DIR="$HOME/tmp/slai-app-dev"
```

## Encrypt a Kubernetes Secret YAML (canonical)

1. Keep plaintext only in **`*.raw.yaml`** (gitignored in your app repo).
2. **`cd` into the clone** so **`sops`** picks up **`.sops.yaml`** (SOPS resolves config from the **current working directory**).

The platform **`.sops.yaml`** matches paths ending in **`.enc\.yaml`**. When the plaintext file has another name, use **`--filename-override`** so the rule applies (same pattern as `slai-app-dev` POC scripts):

```bash
SLAI_APP_DEV_DIR="${SLAI_APP_DEV_DIR:-/tmp/${USER:-user}/slai-app-dev}"
RAW=/path/to/your-app/secrets.raw.yaml
OUT=/path/to/your-app/secrets.enc.yaml   # staging file; copy ciphertext into deploy/apps/<app_id>/ on slai-app-dev PR branch

cd "$SLAI_APP_DEV_DIR"
sops encrypt \
  --filename-override "deploy/apps/your-app-id/secrets.enc.yaml" \
  --input-type yaml \
  "$RAW" > "$OUT"
```

Replace **`your-app-id`** with the real **`app_id`** (must match **`deploy/apps/<app_id>/`** in the PR).

3. **Application repo `.gitignore`:** merge these lines if missing (see **[platform-context.md](platform-context.md)** § *Application repo `.gitignore`*):

```gitignore
*.enc.yaml
*.raw.yaml
.env
```

4. Copy **`secrets.enc.yaml`** into your **`slai-app-dev`** branch under **`deploy/apps/<app_id>/`** and open the PR. **Never** commit **`*.raw.yaml`** or paste **`sops -d`** output into tickets or chat.

## Optional: `encrypt-secrets-yaml.sh` (Linux amd64)

Same outcome as above; fails on non-Linux unless **`sops`** is already on **`PATH`** (or **`SOPS_BIN`** set):

```bash
chmod +x /path/to/skills/app-platform/scripts/encrypt-secrets-yaml.sh
/path/to/skills/app-platform/scripts/encrypt-secrets-yaml.sh \
  --app-id your-app-id \
  --raw /path/to/your-app/secrets.raw.yaml \
  --out /path/to/your-app/secrets.enc.yaml
```

(`--out` is optional; default is **`*.enc.yaml`** next to **`--raw`**.)

You must still **merge `.gitignore` lines** (step 3) yourself -- the script does not edit **`.gitignore`**.

## Private age key

**Encrypting** with the platform **`.sops.yaml`** uses the **public** age recipient only -- **no private key** on your machine.

Decrypting or in-place editing still requires the **age private key** (platform-managed: e.g. GitHub **`SOPS_AGE_KEY`**, or local path per **`slai-app-dev`** docs). This skill does not store or generate that key.

## Summary for agents

- **Assume nothing** about sibling folders named `slai-app-dev`.
- If the app has **any** secret, produce **`secrets.enc.yaml`** using **this document** (or the optional script on supported hosts) -- do not stop at **`*.example`** only.
- **Ensure** a clone exists at **`SLAI_APP_DEV_DIR`**, then **`chmod 700 "$SLAI_APP_DEV_DIR"`** (clone snippet above, or the optional script).
- **Merge** **`*.enc.yaml`**, **`*.raw.yaml`**, **`.env`** into the app repo **`.gitignore`** by hand -- no helper script.
