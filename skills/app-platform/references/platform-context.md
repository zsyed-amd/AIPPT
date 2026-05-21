# What app developers need (SLAI app platform)

**Paths in backticks** under **`deploy/`**, **`scripts/`**, etc. are **relative to the `slai-app-dev` repository root** (not inside `skills/app-platform/`). If you only have an **application repo**, treat `slai-app-dev` as a **separate clone** -- see **[sops-slai-app-dev-clone.md](sops-slai-app-dev-clone.md)** for a **`/tmp/$USER/slai-app-dev`** (or **`SLAI_APP_DEV_DIR`**) workflow; **do not assume** the platform repo exists beside your app.

**Out of scope here:** age-key rotation, GitHub Actions secret wiring, kubeconfig, cluster admin -- ask **platform maintainers** or see platform repo root **`specs/`** / **`docs/`** if you own that.

## Where things live

- **GitHub:** `AMD-SLAI/slai-app-dev` -- open **PRs** with manifests under `deploy/apps/<app_id>/`.
- **Cluster / namespace (POC):** `atl-uc0`, `slai-security-infrastructure-dev`.
- **Harbor:** `mkmhub.amd.com/hw-slai-dev/<image>:<tag>` -- use an **immutable** tag (e.g. full git SHA).

## Repo paths you touch

| Path | Purpose |
|------|---------|
| `deploy/apps/<app_id>/` | Your **`deployment.yaml`**, **`service.yaml`**, **`secrets.enc.yaml`**, optional **`networkpolicy.yaml`** |
| `deploy/README.md` | **One app folder per PR** (unless platform CI says otherwise), glossary |
| App repo **build-image** script | Local **build only** (no Harbor login) -- **template:** skill **`assets/templates/build-image.sh.example`** |
| App repo **publish-image-harbor** script | **Build + push** to Harbor; writes **`.cache/harbor-last-image.env`** -- **template:** skill **`assets/templates/publish-image-harbor.sh.example`** |
| `.env.example` | Copy to **`.env`** (gitignored) for **`IMAGE_*`**, **`HARBOR_*`**, **`BUILD_CONTEXT`** -- **template:** skill **`assets/templates/dot-env.harbor.example`** |
| `docs/publish-image-to-harbor.md` | How to run the publish script |
| `docs/platform-deploy-github-actions.md` | **Platform deploy** workflow, **`main`** vs **`dev`** |

**In your application repository** (separate from `slai-app-dev`), typical paths:

| Path | Purpose |
|------|---------|
| `deploy/slai-app-dev/<app_id>/deployment.yaml` | Handoff **`deployment.yaml`**; **`image:`** updated after Harbor push |
| `deploy/slai-app-dev/<app_id>/service.yaml` | Handoff **`service.yaml`** |
| `deploy/slai-app-dev/<app_id>/secrets.enc.yaml` | SOPS ciphertext -- **commit** (use **`.gitignore`** exception; see **SKILL.md** §0d) so **Deploy prod** can copy it |
| `.github/workflows/deploy-prod.yml` | **Manual CI:** Harbor + sync handoff -> PR to **`slai-app-dev`** -- **`SKILL.md`** §1c (**PAT** + **Actions** secrets on **this** repo) |
| `.cache/harbor-last-image.env` | **Gitignored.** After **`publish-image-harbor.sh`**: **`FULL_IMAGE=...`** |

**After your PR merges:** someone with access runs **Actions -> Platform deploy (git + Harbor)** with your **`app_id`** (or **`gh workflow run ...`**). You do **not** need cluster credentials for that step.

## Branches and URLs

- **`main`** -> prod-style manifests -> **`https://<app_id>.app-platform.amd.com/`**
- **`dev`** -> dev manifests -> **`https://<app_id>.app-platform-dev.amd.com/`**
- Run **Platform deploy** from the branch that matches where you want the change to land.
- If **`origin/dev`** does **not** exist on **`AMD-SLAI/slai-app-dev`** (shallow clone or repo layout), open PRs against **`main`** -- fetch **`dev`** only when the remote branch is present.

**Ingress / DNS:** platform uses **wildcard DNS/TLS** for those zones; you still set a concrete **Ingress `host`** and IdP redirect URIs. **`ingressClassName`** may be empty until Eng IT documents it.

## OpenTelemetry (set in your Deployment)

| | |
|--|--|
| **OTLP** | `http://atlvslaiapp03:4317` (gRPC **4317**) |
| **Typical env** | `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, optional `OTEL_RESOURCE_ATTRIBUTES` |

If pods cannot resolve **`atlvslaiapp03`**, ask platform/observability for an FQDN. Do **not** put collector tokens in the container image; if auth headers are required later, they go through **SOPS** like other secrets.

## Secrets (SOPS) -- app team part only

- **`secrets.enc.yaml`** under **`deploy/apps/<app_id>/`** on branch in **`slai-app-dev`**: **ciphertext** committed to git.
- Edit plaintext locally as **`*.raw.yaml`** (gitignored in your app repo), then encrypt with **`sops`** using the platform repo's **`.sops.yaml`** (public **age** recipient at **`slai-app-dev`** root).
- **Do not assume** you already have **`slai-app-dev`** checked out next to your app. **Generate ciphertext** by following **[sops-slai-app-dev-clone.md](sops-slai-app-dev-clone.md)** (**clone** + **`sops encrypt`**). Optionally use **[`../scripts/encrypt-secrets-yaml.sh`](../scripts/encrypt-secrets-yaml.sh)** on **Linux amd64**. Agents **must** produce **`secrets.enc.yaml`** when the app uses secrets, not only templates.
- **Never** commit **`client_secret`**, Harbor tokens, or **age private keys** as plaintext.

## Application repo `.gitignore`

In the **application** repository (not **`slai-app-dev`**): merge **`*.raw.yaml`**, **`.env`**, and a pattern that ignores stray **`*.enc.yaml`** but **allows** **`deploy/slai-app-dev/**/secrets.enc.yaml`** so **Deploy prod** can read committed ciphertext -- see **SKILL.md** §0d.

## Harbor credentials

- Use **`HARBOR_USERNAME`** / **`HARBOR_PASSWORD`** (robot) on the machine that runs **`publish-image-harbor.sh`** -- env or **`.env`**, never committed.
- **No robot?** Open a **GitHub Issue** on **`AMD-SLAI/slai-app-dev`** (or your program intake) with app repo, desired **`hw-slai-dev/<IMAGE_NAME>`**, workstation vs CI push, team contact. Platform may issue a **dedicated** or **shared** robot per policy.

## PR rules

- **One** `deploy/apps/<app_id>/` directory per PR unless platform **CI** requires otherwise.
- Do **not** paste **`sops -d`** output or raw secrets into chat or tickets.

## Glossary

- **`app_id`:** folder name **`deploy/apps/<app_id>/`** on **`slai-app-dev`** (and handoff **`deploy/slai-app-dev/<app_id>/`** in the application repo).
- **DNS label:** usually equals **`app_id`** -- leftmost label in **`https://<label>.app-platform.amd.com/`**.

## Workstation: Podman / Pandora

Some AMD hosts need **`podman --runtime /tool/pandora/.package/runc-*/bin/runc`** for **login** / **build** / **push**. Rootless build may need **`--storage-opt overlay.ignore_chown_errors=true`**. More detail: **[references/guidelines.md](guidelines.md)** § *Podman / Pandora*.
