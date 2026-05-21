---
name: app-platform
description: 'End-to-end: phrases like deploy my app, submit to app-platform, or onboard
  to slai-app-dev map to the same flow -- new or existing web app -> OTel (default)
  + Okta question -> Dockerfile -> early: cp .env.example -> .env; gate on Harbor
  robot creds from slai-app-dev maintainers (stop with what-is-next guidance if missing)
  -> deployment.yaml + service.yaml + secrets.enc.yaml -> SOPS encrypt raw secret
  -> Harbor publish -> stamp image from .cache/harbor-last-image.env into deployment.yaml
  -> only then PR on AMD-SLAI/slai-app-dev. Do not open the platform PR with a placeholder
  image. Ongoing redeploys: copy deploy-prod.yml -- manual CI rebuilds, republishes
  to Harbor, and opens a new slai-app-dev PR that syncs committed handoff manifests
  (deployment, service, optional secrets/networkpolicy) and stamps the image. Optional
  encrypt-secrets-yaml.sh (Linux amd64). Templates for YAML, Harbor scripts, and deploy-prod
  workflow.'
license: Copyright (c) Advanced Micro Devices, Inc., or its affiliates. All rights
  reserved. Portions of this content consists of AI generated content.
metadata:
  author: ctung
  version: "0.0.8"
  category: devops
  tags:
  - harbor
  - kubernetes
  - sops
  - slai-app-dev
  - deployment
  - docker
  - okta
  - oauth
  - opentelemetry
  compliance_scan:
    status: PASSED
    risk_score: 20
    risk_level: LOW
    scan_date: '2026-03-31T11:13:36.300798+00:00'
compatibility:
  universal: true
---
# app-platform

End-to-end assistant for **web/app teams** shipping a container to the **SLAI app platform** managed in **`github.com/AMD-SLAI/slai-app-dev`**: **OTel + Okta decision -> containerize -> manifests + SOPS -> Harbor publish -> stamp `FULL_IMAGE` in `deployment.yaml` -> PR to `slai-app-dev` -> Platform deploy**. **`slai-app-dev` PRs must not ship placeholder `image:`** -- wait for a successful registry push first. For **repeat releases**, the **application** repo should include **`Deploy prod`** (**`.github/workflows/deploy-prod.yml`**, **`workflow_dispatch`**): rebuild -> Harbor push -> PR on **`slai-app-dev`** that **copies** the committed handoff tree (**`deploy/slai-app-dev/<app_id>/`**) into **`deploy/apps/<app_id>/`** ( **`deployment.yaml`**, **`service.yaml`**, **`secrets.enc.yaml`**, **`networkpolicy.yaml`** when present), then **stamps** **`deployment.yaml`** **`image:`** to the pushed **`FULL_IMAGE`**. Any edit under handoff is therefore resubmitted.

## Primary user intents (same skill for all of these)

Users may say any of the following -- treat them as **the same end-to-end workflow** (OTel + Okta -> container -> manifests + SOPS -> Harbor publish -> stamp **`FULL_IMAGE`** -> PR):

- *"Help me **build** a web app and **publish** it to the app platform."* (**greenfield** -- scaffold or extend app code, **Dockerfile**, then full sequence.)
- *"Help me **publish** / **deploy** **this existing** web app to the app platform."* (**brownfield** -- harden or add **Dockerfile** and manifests, same path.)
- *"**Deploy my app**"*, *"**Ship** my app to **SLAI** / **app-platform**"*, *"**Submit** my app **to the app platform**"*, *"**Onboard** this app to **slai-app-dev**"* -- assume they mean **container + Harbor + Kubernetes PR** unless they specify they only want one piece (e.g. Dockerfile review only).

In every case the agent should **complete the full handoff** through an **`slai-app-dev` PR** when the environment allows (git, **GitHub** auth, **Harbor** credentials, **SOPS**). **First**, follow **§0e** (copy **`.env.example` -> `.env`**, verify **`HARBOR_*`**, **stop** with a clear **"What you need to do next"** if robots are missing -- **do not** continue the same turn with publish/PR scaffolding). **Open that PR only after** **`publish-image-harbor.sh`** (or equivalent) **succeeds** and **`deployment.yaml`** **`image:`** is set to the stamped **`FULL_IMAGE`**. If Harbor cannot run here (no robot, no network), **do not** open a platform PR with **`YOUR_GIT_SHA`** / placeholders -- stop with exact publish, stamp, and PR steps for the user.

## When to use this skill

Invoke when the user (or task) involves any of:

- **First-time** deploy of a web app to **`slai-security-infrastructure-dev`** via **Platform deploy**
- **Dockerfile** / **container** hardening for **linux/amd64**, **restricted** clusters
- **Harbor** push to **`mkmhub.amd.com/hw-slai-dev/<image>:<git-sha>`**
- **SOPS + age** for **`secrets.enc.yaml`** committed under **`deploy/apps/<app>/`**
- **Okta / OIDC** for browser SSO -- redirect URIs on **`*.app-platform*.amd.com`**
- **OpenTelemetry** -- OTLP endpoint, **`OTEL_SERVICE_NAME`**, minimal **HTTP** semantic conventions
- Authoring **`deployment.yaml`** + **`service.yaml`** + opening a **PR** on **`slai-app-dev`**
- **`workflow_dispatch`** **Platform deploy (git + Harbor)** or **`gh workflow run`**
- **Application-repo `deploy-prod`** workflow (rebuild + Harbor + PR to **`slai-app-dev`**) -- template **[`assets/templates/deploy-prod.yml.example`](assets/templates/deploy-prod.yml.example)**

Do **not** use this skill to fabricate **production secrets**, **kubeconfigs**, or **private keys**.

**Secrets workflow:** **`secrets.enc.yaml`** (SOPS) is **always** part of the three-file PR bundle. Create a gitignored **`*.raw.yaml`** (real secrets or minimal placeholder **`Secret`** if nothing is confidential), encrypt via **[sops-slai-app-dev-clone.md](references/sops-slai-app-dev-clone.md)** (or optional **`encrypt-secrets-yaml.sh`** on **Linux amd64**). Do not commit **`*.raw.yaml`** or paste **`sops -d`** output. If **`sops`** / **`git clone`** cannot run here, give exact user commands; do not claim the handoff is complete without ciphertext in the PR branch.

## Quick reference (skill-local)

| Topic | Where to read |
|-------|----------------|
| Repo paths, branches, URLs, OTel values, Harbor Issues | **[references/platform-context.md](references/platform-context.md)** |
| SOPS when app repo ≠ `slai-app-dev`; generate **`secrets.enc.yaml`** | **[references/sops-slai-app-dev-clone.md](references/sops-slai-app-dev-clone.md)** (canonical); optional **[scripts/encrypt-secrets-yaml.sh](scripts/encrypt-secrets-yaml.sh)** (Linux amd64 helper) |
| Application **`.gitignore`** (`*.enc.yaml`, ...) | **[references/platform-context.md](references/platform-context.md)** § *Application repo `.gitignore`* -- merge lines in markdown; no script |
| Dockerfile / Deployment hardening, Podman quirks (incl. **`chown`/`COPY --chown`** failures, docker-only publish anti-pattern) | **[assets/templates/deployment.yaml.example](assets/templates/deployment.yaml.example)**, **[references/guidelines.md](references/guidelines.md)** |
| Harbor **build** / **publish** shell scripts | **[build-image.sh.example](assets/templates/build-image.sh.example)**, **[publish-image-harbor.sh.example](assets/templates/publish-image-harbor.sh.example)**, **[dot-env.harbor.example](assets/templates/dot-env.harbor.example)** |
| **Deploy prod** (app repo CI: Harbor + PR) | **[deploy-prod.yml.example](assets/templates/deploy-prod.yml.example)** |
| Okta / OAuth / XAA | **[references/okta-oauth-web.md](references/okta-oauth-web.md)**, **[assets/templates/okta-registration.yaml.example](assets/templates/okta-registration.yaml.example)** |
| HTTP OTel attributes (minimal) | **[references/otel-web-semconv.md](references/otel-web-semconv.md)** |
| NetworkPolicy / egress | **[references/network-egress.md](references/network-egress.md)**, **[assets/templates/networkpolicy.yaml.example](assets/templates/networkpolicy.yaml.example)** |
| All skill files | **[references/platform-links.md](references/platform-links.md)** |

**Platform repo:** `AMD-SLAI/slai-app-dev`. Maintainer-only topics (CI secrets, key rotation, cluster RBAC) live in repo root **`specs/`** / **`docs/`** -- not in this skill.

## End-to-end sequence (agents -- default order)

Work **in order** unless the user already finished a step (e.g. Dockerfile exists). Confirm **stack**, **`app_id`**, **Harbor `IMAGE_NAME`**, **listen port**, and target branch (**`main`** vs **`dev`**) for **`slai-app-dev`**.

**Gate -- no `slai-app-dev` PR until the real image exists:** Do **not** **`gh pr create`** / push a branch with **`deploy/apps/<app_id>/deployment.yaml`** until **Harbor publish** has **succeeded** and that file's **`spec.template.spec.containers[].image`** is the exact **`FULL_IMAGE`** from **`.cache/harbor-last-image.env`** (or publish script output). Do **not** land a mergeable manifest PR whose **`image:`** is still a placeholder after publish.

0. **Harbor `.env` bootstrap + robot gate** -> **§0e** (**first** in the **application** repo): ensure **`.env.example`** exists, then **`cp -n .env.example .env`** (do **not** overwrite an existing **`.env`**). Tell the user to obtain **Harbor robot** credentials from the **maintainers of `AMD-SLAI/slai-app-dev`** (GitHub Issue on that repo -- see **§0e** / **§1** / **platform-context** § *Harbor robots*). **Verify `HARBOR_USERNAME` and `HARBOR_PASSWORD` are non-empty** in **`.env`**. If **either is missing**: **stop** after a prominent **"What you need to do next"** block -- **do not** continue the **same assistant turn** with **`publish-image-harbor.sh`**, image stamping, or **`slai-app-dev`** PR work; **do not** bury this under long unrelated output. The user continues in a **follow-up** once **`.env`** is filled. **Exception:** the user explicitly requests **issue-only text**, **no Harbor yet**, or **scaffold-only** -- then skip publish/PR per their scope only.
1. **Okta?** -> **§0a** (ask; if yes, plan **`client_secret`** only in SOPS + **`deployment.yaml`** wiring per **okta-oauth-web.md**).
2. **OpenTelemetry** -> **§0b** (default **on**; inject **`OTEL_*`** into **`deployment.yaml`** unless user opts out).
3. **Egress / NetworkPolicy?** -> **§0c** (ask; add **`networkpolicy.yaml`** when non-default egress is needed).
4. **`.gitignore`** -> **§0d** in the **application** repo (`*.enc.yaml`, `*.raw.yaml`, `.env`).
5. **Containerize** -> **§1**: **`Dockerfile`** (**`linux/amd64`**, non-root, **`/healthz`** or equivalent); copy Harbor script **templates** into **`scripts/`** + **`.env.example`** if missing. **Default (greenfield / full onboard):** add **`Deploy prod`** in the **application** repo now -- copy **[`assets/templates/deploy-prod.yml.example`](assets/templates/deploy-prod.yml.example)** -> **`.github/workflows/deploy-prod.yml`** (**§1c**). Commit the workflow file even if the maintainer must still wire **Actions secrets/variables** ( **`SLAI_APP_DEV_PR_TOKEN`**, **`HARBOR_*`**, **`APP_ID`**, **`IMAGE_NAME`**, **`BUILD_CONTEXT`** ) in the GitHub UI. **Skip** only if the user opts out, the app repo has no GitHub Actions, or policy forbids it.
6. **Two plaintext manifests** -> **§1b**: **`deployment.yaml`** + **`service.yaml`** (from templates) with **OTel** env, probes, **`secretKeyRef`** / **`envFrom`** as needed. A temporary **`image:`** placeholder is OK **only** in the **application** repo handoff (**`deploy/slai-app-dev/<app_id>/`**) **while** iterating -- **replace with `FULL_IMAGE` after publish** before **any** copy into **`AMD-SLAI/slai-app-dev`**.
7. **Third manifest (SOPS)** -> **§3**: maintain **`*.raw.yaml`** (gitignored); **always** produce **`secrets.enc.yaml`** -- the platform bundle is **three** files. If there are no confidential values, use a minimal **`Secret`** (e.g. single operational key) per team policy, still encrypt.
8. **Publish** -> run **`publish-image-harbor.sh`** (requires **§0e** satisfied); then **read** **`.cache/harbor-last-image.env`** and set **`deployment.yaml`** **`image:`** to **`FULL_IMAGE`** everywhere it will ship (**§1**, app handoff + **`slai-app-dev`** branch).
9. **Validate** (optional) -> **`python3 skills/app-platform/scripts/main.py deploy/apps/<app_id>`** from **`slai-app-dev`** checkout (**Example B**).
10. **Open a PR** -> **§4a** against **`AMD-SLAI/slai-app-dev`** with **`deploy/apps/<app_id>/`** containing all **three** files (**§4** rules) and a **real** **`image:`**.
11. **Redeploy path (verify)** -> After the first platform PR merges, confirm **`Deploy prod`** exists on the **application** repo (step **5**). Walk the user through **§1c** (fine-grained PAT + **Actions** secrets on the **application** repo). **Ongoing:** **Actions -> Deploy prod -> Run workflow** -> merge the automated PR on **`slai-app-dev`** -> **Platform deploy** (**§5**).

## Golden-path workflow (agent checklist -- reference detail)

Work **in order** with the **end-to-end sequence** above as the spine. Confirm assumptions with the user (stack, app id, Harbor image name, listen port).

### 0e. Harbor `.env` bootstrap + robot credential gate (do this first in the app repo)

**Goal:** The user always has a concrete **`.env`** to edit, always knows **who** issues Harbor robots, and never lands in a long workflow without knowing the next action.

1. From the **application repository root** (where **`publish-image-harbor.sh`** / **`.env.example`** live): if **`.env.example`** is missing, create it from **[`assets/templates/dot-env.harbor.example`](assets/templates/dot-env.harbor.example)** (adjust **`IMAGE_NAME`**, **`BUILD_CONTEXT`**).
2. If **`.env`** does not exist, run **`cp -n .env.example .env`** (POSIX). If **`cp -n`** is unavailable, copy only when **`.env`** is absent -- **never** overwrite an existing **`.env`**.
3. **Tell the user (in prose, near the top of the reply):** *You need **Harbor robot** credentials (**`HARBOR_USERNAME`**, **`HARBOR_PASSWORD`**) for **`mkmhub.amd.com/hw-slai-dev/<IMAGE_NAME>`**. Request them from the **maintainers of [`AMD-SLAI/slai-app-dev`](https://github.com/AMD-SLAI/slai-app-dev)** -- typically by opening a **GitHub Issue** on that repo (see **§1** / **[references/platform-context.md](references/platform-context.md)** § *Harbor robots*). Paste the values into **`.env`** (gitignored); **never** commit them.*
4. **Verify** both **`HARBOR_USERNAME`** and **`HARBOR_PASSWORD`** are set to **non-empty** values in **`.env`** (read the file or `set -a; source .env`; **never** print secret values or paste them into chat).
5. **If verification fails:** **Stop** after a dedicated **"What you need to do next"** section that includes:
   - **Edit** **`.env`** in the app repo and set **`HARBOR_USERNAME`** and **`HARBOR_PASSWORD`** from the **slai-app-dev** maintainers.
   - **Where to ask:** **[`AMD-SLAI/slai-app-dev` Issues](https://github.com/AMD-SLAI/slai-app-dev/issues)** (or your program's intake); include **app repo**, intended **`IMAGE_NAME`**, **workstation vs CI** push, **team / contact** -- see **§1** bullet *No robot yet?*
   - **When done:** Ask the agent to continue (or re-run the deploy flow); **then** the agent proceeds with **§0a** onward and eventually **`publish-image-harbor.sh`**.
   **Do not** in the **same turn**: run **`publish-image-harbor.sh`**, push to Harbor, stamp **`deployment.yaml`** for merge, or open **`slai-app-dev`** PRs that assume the image exists.
6. **If verification succeeds:** Continue with **§0a** (Okta) and the rest of the sequence.

### 0a. OAuth / Okta (browser SSO)

**Ask:** *Will **browser users** sign in with **corporate SSO (Okta / OIDC)**?*

- **If no:** Skip to § 0b unless they need other auth (document only on request).
- **If yes:** Follow **[references/okta-oauth-web.md](references/okta-oauth-web.md)**:
  - **Standard confidential OIDC client** (authorization code + **client secret** on the server) -- **no DCR**, **no MCP BFF** pattern.
  - Clarify **server-rendered** vs **SPA + public client (PKCE)** when applicable.
  - **REST API:** validate **`Authorization: Bearer`** for **Okta access tokens** and **XAA** tokens per **`iss` / `aud`** / JWKS; see **okta-oauth-web.md** § *XAA reference material* for public references and Eng IT / program docs.
  - Set **redirect / logout URIs** on planned hosts **`https://<app_id>.app-platform.amd.com/...`** and **`https://<app_id>.app-platform-dev.amd.com/...`** (see **[references/platform-context.md](references/platform-context.md)** § *Public URLs and ingress*).
  - For **declarative Okta YAML**, use **[`assets/templates/okta-registration.yaml.example`](assets/templates/okta-registration.yaml.example)** as a starting shape and **[references/okta-oauth-web.md](references/okta-oauth-web.md)** for rules (confidential web client, app-platform redirect URIs only; no MCP-only fields).
  - Put **`client_secret`** only in **`secrets.enc.yaml`** (SOPS), referenced as **`env`** from **`deployment.yaml`**.

### 0b. OpenTelemetry (default on)

**Unless the user explicitly opts out**, plan to **inject OTLP** so traces/metrics reach the platform collector:

- Set **`OTEL_EXPORTER_OTLP_ENDPOINT`**, **`OTEL_SERVICE_NAME`**, and optional **`OTEL_RESOURCE_ATTRIBUTES`** per **[references/platform-context.md](references/platform-context.md)** § *Observability* (recorded endpoint **`http://atlvslaiapp03:4317`**).
- Prefer **auto-instrumentation** for the stack; use **[references/otel-web-semconv.md](references/otel-web-semconv.md)** for the **minimal stable HTTP** attribute set (links to OpenTelemetry **HTTP semconv**).
- Add the **`env`** block to **`deployment.yaml`** (see **[assets/templates/deployment.yaml.example](assets/templates/deployment.yaml.example)**); never put collector secrets in the image.

### 0c. Egress / downstream dependencies (MySQL, APIs, ...)

**Ask:** *From inside the pod, does the app connect to **MySQL**, **other databases**, or **specific TCP services** (not already covered by ingress-only flows)?*

- If **yes**, add **`networkpolicy.yaml`** using **[`assets/templates/networkpolicy.yaml.example`](assets/templates/networkpolicy.yaml.example)**. **Whitelist-only egress:** default allows **only DNS (:53)** + **OTLP TCP :4317** (recorded **`http://atlvslaiapp03:4317`**, **platform-context.md** § *Observability*) -- **every other port** (MySQL, HTTPS, ...) needs an **explicit egress rule**. See **[`references/network-egress.md`](references/network-egress.md)**.
- **Harbor** pulls are **not** pod egress -- no rule needed for the registry for normal **`imagePull`**.

### 0d. Application repository `.gitignore` (not `slai-app-dev`)

When working in an **application** repository (any repo that is **not** the **`AMD-SLAI/slai-app-dev`** checkout):

- **Create or edit `.gitignore` in markdown-driven workflow** (no helper script): ensure these lines exist (merge with existing patterns; avoid duplicates):
  - **`*.raw.yaml`** -- plaintext secrets
  - **`.env`** -- Harbor / local credentials
  - **Encrypted YAML in the app repo:** ignore generic **`*.enc.yaml`**, but **track** the handoff ciphertext so **`Deploy prod`** can copy it -- add an **exception** for your path (convention **`deploy/slai-app-dev/<app_id>/secrets.enc.yaml`**), e.g.
    - **`*.enc.yaml`**
    - **`!deploy/slai-app-dev/**/secrets.enc.yaml`**
- On **`slai-app-dev`**, **`deploy/apps/<app_id>/secrets.enc.yaml`** (SOPS ciphertext) **is** committed -- do not add repo-root **`*.enc.yaml`** ignores that would untrack those files (**platform repo** `.gitignore` differs from the application repo).

### 1. Container image (app repo)

- Ensure a **`Dockerfile`** that builds **`linux/amd64`**, runs **non-root** where possible, and exposes a **health** path (e.g. **`/healthz`**) aligned with probes later.
- Prefer **immutable** tags: **full git SHA** after publish (not **`:latest`** for anything you must roll back). When the app directory has **no** **`.git`**, **`publish-image-harbor.sh`** falls back to **`local-<timestamp>`** -- that tag is still valid for **`deployment.yaml`** once Harbor push succeeds; prefer initializing a git repo / CI publish for **SHA** tags when you can.
- **Do not** replace **`publish-image-harbor.sh`** with a **docker-only** script: many workstations have **`podman`** (e.g. Pandora) but **no** **`docker`** in **`PATH`**. Always copy the full template (**Docker** when available, else **Podman** + Pandora **`runc`** paths) -- **[`assets/templates/publish-image-harbor.sh.example`](assets/templates/publish-image-harbor.sh.example)**.
- **Podman / NFS / overlay builds -- `chown` to `65534`:** **`RUN chown -R 65534:65534 ...`** and **`COPY --chown=65534:65534`** can fail with **`invalid argument`** / **`lchown`** on some hosts. **Workaround:** skip image **`USER`** / ownership changes; keep application files **world-readable** (**`0644`**); enforce **`runAsUser`**, **`runAsGroup`**, **`fsGroup` `65534`** in **`deployment.yaml`** only. See **[`references/guidelines.md`](references/guidelines.md)** § *Podman / overlay and Dockerfile ownership*.
- **Harbor scripts (templated in this skill):** When creating a new app repo, copy the canonical templates into **`scripts/`** (then **`chmod +x`**):
  - **[`assets/templates/build-image.sh.example`](assets/templates/build-image.sh.example)** -> app repo **`scripts/`** **`build-image.sh`** (copy target; see **§1**)
  - **[`assets/templates/publish-image-harbor.sh.example`](assets/templates/publish-image-harbor.sh.example)** -> app repo **`scripts/`** **`publish-image-harbor.sh`** (copy target; see **§1**)
  - **[`assets/templates/dot-env.harbor.example`](assets/templates/dot-env.harbor.example)** -> **`.env.example`** (adjust **`IMAGE_NAME`**, **`BUILD_CONTEXT`**)
  The **`AMD-SLAI/slai-app-dev`** repo root also keeps **build-image** and **publish-image-harbor** shell scripts under **`scripts/`** -- **keep them aligned** with these templates when behavior changes (templates are the source of truth for new apps).
- **Already have scripts?** Keep using them; only replace when onboarding or when you need template updates (Podman/Harbor stamp, etc.).
- **After every successful Harbor push,** **`publish-image-harbor.sh`** writes **`.cache/harbor-last-image.env`** (under the app repo root; **`.cache/`** is gitignored) with **`FULL_IMAGE=...`** and **`IMAGE_TAG=...`**. **Immediately** read that file (or the **`Pushed mkmhub...`** line in the script output) and set **`deployment.yaml`** **`spec.template.spec.containers[].image`** to **`FULL_IMAGE`** exactly -- do not leave **`YOUR_GIT_SHA`** / placeholder **`image:`** once a push has succeeded. Optional env **`HARBOR_LAST_IMAGE_FILE`** overrides the stamp path.
- **Harbor:** target **`mkmhub.amd.com/hw-slai-dev/<image>:<tag>`**; use a **robot** (**`HARBOR_USERNAME`** / **`HARBOR_PASSWORD`**) from CI or local env -- **never** commit tokens.
- **No robot yet?** See **§0e**: the user must obtain robots from **slai-app-dev maintainers**. File a **GitHub Issue** on **`AMD-SLAI/slai-app-dev`** (Issues tab on the platform repo) asking for **Harbor robot credentials** for this app's OCI repository under **`hw-slai-dev`**. Include at minimum: **application repo** URL (or name), **intended Harbor image name** (the **`IMAGE_NAME`** segment in **`mkmhub.amd.com/hw-slai-dev/<IMAGE_NAME>:<tag>`**), whether you need **push** from **developer workstations**, **CI**, or both, and **team / contact**. Policy summary: **[references/platform-context.md](references/platform-context.md)** § *Harbor robots*. If your program uses **ServiceNow** (or another intake) instead of GitHub Issues, use that path but attach the same details.

### 1b. `deployment.yaml` + `service.yaml` (when creating the app)

- As soon as the app exists, add a handoff tree in the **application** repo (convention: **`deploy/slai-app-dev/<app_id>/`**) containing **`deployment.yaml`** and **`service.yaml`** ready to copy into **`AMD-SLAI/slai-app-dev`** as **`deploy/apps/<app_id>/`**.
- **Author these files from the skill templates** -- **[`assets/templates/deployment.yaml.example`](assets/templates/deployment.yaml.example)** and **[`service.yaml.example`](assets/templates/service.yaml.example)** -- substituting **`app_id`**, **`IMAGE_NAME`**, **`containerPort`**, probes, **OTEL** `env`, **`secretKeyRef`**, etc. Follow **[`references/guidelines.md`](references/guidelines.md)**. **Do not introduce separate scaffolding scripts** for this; the assistant writes the YAML from the templates and this skill.
- **`image:`** may use a placeholder **only** while drafting in the **application** repo; **`AMD-SLAI/slai-app-dev`** must receive **`deployment.yaml`** **after** Harbor publish, with **`FULL_IMAGE`** from **`.cache/harbor-last-image.env`** (§1). Do **not** treat "placeholder until merge" as acceptable on the platform PR.

### 1c. **`Deploy prod`** workflow (application repo -- redeploys + manifest sync)

Copy **[`assets/templates/deploy-prod.yml.example`](assets/templates/deploy-prod.yml.example)** to **`.github/workflows/deploy-prod.yml`** in the **application** repository (not **`slai-app-dev`**). **Agents:** add this file during **greenfield** onboarding (sequence step **5**).

**What it does:** on **`workflow_dispatch`**, Actions **builds** the app **`Dockerfile`** (**`linux/amd64`**), **pushes** **`${{ github.sha }}`** to Harbor, clones **`slai-app-dev`**, **copies** the **committed** handoff directory (default **`deploy/slai-app-dev/<APP_ID>/`**) into **`deploy/apps/<APP_ID>/`** -- **`deployment.yaml`**, **`service.yaml`**, and **`secrets.enc.yaml`** / **`networkpolicy.yaml`** when those files exist in handoff -- then **`yq`** sets **`deployment.yaml`** **`spec.template.spec.containers[0].image`** to the pushed **`FULL_IMAGE`**, commits, pushes a branch, and **`gh pr create`**. Any change committed under handoff is therefore **resubmitted** on the platform PR.

**Handoff + `secrets.enc.yaml`:** commit SOPS ciphertext under **`deploy/slai-app-dev/<app_id>/secrets.enc.yaml`** and use **§0d** **`*.enc.yaml`** exception so **`Deploy prod`** can read it.

#### How to create the PAT (browser) and add it as an Actions secret

**`gh` cannot mint PATs** -- the human does this once per app repo (or team policy). Official: [Creating a fine-grained personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token).

1. On **GitHub.com**, open your **personal** account (**profile avatar** -> **Settings**). If you land in **org** settings, switch to **your user** -- fine-grained PATs are created under **your** user.
2. **Developer settings** -> **Personal access tokens** -> **Fine-grained tokens** -> **Generate new token**.
3. **Name / expiration:** e.g. `slai-app-dev-deploy-prod-pr` -- per org policy.
4. **Resource owner:** the **org** that owns **`AMD-SLAI/slai-app-dev`** (e.g. **`AMD-SLAI`**).
5. **Repository access:** **Only select repositories** -> **`slai-app-dev`** **only** (not "All repositories").
6. **Permissions** (for **`slai-app-dev`** only): **Contents** -> **Read and write**; **Pull requests** -> **Read and write**; everything else **No access** unless Eng documents an exception.
7. **Generate token**, **copy** the string **once**.
8. **SAML SSO:** if the org uses SSO, open the token in the list -> **Configure SSO** / **Authorize** for **`AMD-SLAI`** -- otherwise **`git push`** / **`gh pr`** returns **403**.
9. On the **application** repository (the repo that **runs** **Deploy prod**): **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**:
   - **`SLAI_APP_DEV_PR_TOKEN`** -- paste the PAT (never commit it).
10. Still under **Actions** secrets, add **`HARBOR_USERNAME`** and **`HARBOR_PASSWORD`** (Harbor robot -- same values as local **`.env`**).
11. **Settings** -> **Secrets and variables** -> **Actions** -> **Variables** tab (same **application** repo): create **`APP_ID`**, **`IMAGE_NAME`**, **`BUILD_CONTEXT`** (optional **`MANIFEST_HANDOFF_REL`**, **`HARBOR_*`**, **`DOCKERFILE`** -- see template header).

**Agents --** Tell the user to complete steps **1-11** in the browser when **`SLAI_APP_DEV_PR_TOKEN`** is missing; never paste the PAT into chat or commit it.

- **Trigger (application repo):** **`workflow_dispatch`** -- human runs **Actions -> Deploy prod -> Run workflow**; choose **`slai_base_ref`** **`main`** or **`dev`**.

- **Order / gate:** Harbor **push** finishes **before** the platform PR is opened (same as §4a).

- **First-time folder on `slai-app-dev`:** if **`deploy/apps/<app_id>/`** does not exist on the base branch yet, the workflow **creates** it from handoff files -- you can still do the first merge via laptop **§4a** if you prefer; after that, **Deploy prod** keeps handoff and platform in sync. **Omission:** dropping a file from handoff does **not** delete it on **`slai-app-dev`** (only present files are copied); remove platform files in a dedicated PR if required.

- **After merge** of the manifest PR on **`slai-app-dev`**: **`Platform deploy (git + Harbor)`** runs automatically when **`deploy/apps/**`** changes on **`main`** or **`dev`**; use **manual** workflow only for a re-deploy without a new merge.

- **Runner:** must reach Harbor (**`ubuntu-latest`** if egress allows).

### 2. `app_id` (folder on `slai-app-dev`)

- **`app_id`** is the directory name **`deploy/apps/<app_id>/`** on **`AMD-SLAI/slai-app-dev`**. It matches **`deploy/slai-app-dev/<app_id>/`** in the **application** repo handoff. There is **no** separate registry or metadata file in this skill -- the folder **is** the source of truth.

### 3. Three manifests under `deploy/apps/<app_id>/` (PR into `slai-app-dev`)

Every app ships **three** core files; add more plaintext YAML as needed (applied in sorted order):

| File | Owner | Notes |
|------|--------|-------|
| **`deployment.yaml`** | **Web/app team** | Full **`image:`** (`registry/project/repo:tag`); probes; labels/selectors; **OTEL** `env`; **`envFrom`** / **`secretRef`** for Okta if used. |
| **`service.yaml`** | **Web/app team** | **ClusterIP** port, **`selector`** matching Deployment labels. |
| **`secrets.enc.yaml`** | **Web/app team** (ciphertext) | Plain **`Secret`** only in gitignored **`*.raw.yaml`**; encrypt with SOPS. Commit ciphertext under **`deploy/slai-app-dev/<app_id>/secrets.enc.yaml`** in the **application** repo (**§0d** `!...` exception) so **Deploy prod** can copy it. **Okta `client_secret`** goes here. |
| **`networkpolicy.yaml`** (recommended) | **Web/app team** | **Egress lockdown**: **DNS**, **OTLP :4317**, **ingress** from controller, plus **each downstream** (e.g. **MySQL :3306**). See **[`references/network-egress.md`](references/network-egress.md)**. |

**Agents -- `secrets.enc.yaml` is always required:** The **three-file** bundle (**`deployment.yaml`**, **`service.yaml`**, **`secrets.enc.yaml`**) must be complete for **`main.py`** and platform deploy. If the app has **no** confidential env (rare), still author a **minimal** **`Secret`** in **`*.raw.yaml`** (e.g. one placeholder or operational key), encrypt it, and ship **`secrets.enc.yaml`**. For normal apps with secrets (demo token, API key, **`DEMO_SECRET`**, Okta **`client_secret`**, ...), put real values only in **`*.raw.yaml`**, never in git.

1. Author plaintext **`Secret`** YAML in a **`*.raw.yaml`** file (gitignored). Never commit it.
2. Encrypt via **[references/sops-slai-app-dev-clone.md](references/sops-slai-app-dev-clone.md)** (**clone** **`slai-app-dev`**, **`chmod 700`**, **`sops encrypt`** with **`--filename-override`**). **Encryption uses only the public recipient** in **`.sops.yaml`** -- no age private key needed. On **Linux amd64**, you may use **`scripts/encrypt-secrets-yaml.sh`** instead (optional; downloads **`sops`** if missing).
3. Merge **§0d** **`.gitignore`** lines in the app repo if not already present.
4. Place the resulting **`secrets.enc.yaml`** under **`deploy/apps/<app_id>/`** on your **`slai-app-dev`** PR branch **when assembling the PR** -- **after** **`deployment.yaml`** on that branch carries **`FULL_IMAGE`** (post-publish), per the **End-to-end sequence** gate.

If **`sops`** / **`git`** are unavailable in the environment, stop with explicit user steps -- do **not** hand off only an example file.

See also **[references/platform-context.md](references/platform-context.md)** § *Secrets (SOPS)*.

Templates (same sources as §1b): **[assets/templates/deployment.yaml.example](assets/templates/deployment.yaml.example)**, **[service.yaml.example](assets/templates/service.yaml.example)**, **[networkpolicy.yaml.example](assets/templates/networkpolicy.yaml.example)**, **[assets/templates/okta-registration.yaml.example](assets/templates/okta-registration.yaml.example)** (Okta admin handoff -- not applied by deploy).

### 4. Pull request rules

- **One** **`deploy/apps/<app_id>/`** tree per PR unless platform **CI** documentation requires splitting (e.g. label **`platform-infra`**).
- Do **not** print decrypted **`sops`** output in chat or CI logs.

### 4a. Open the pull request on `slai-app-dev` (required handoff)

The workflow is **not complete** until a PR exists (or you give the user an exact **`gh`** / **GitHub UI** recipe they can run).

- **Prerequisite:** **`publish-image-harbor.sh`**, **`deploy-prod`**, or your **CI equivalent** has **finished successfully** and **`deploy/apps/<app_id>/deployment.yaml`** on the PR branch has **`image:`** = **`FULL_IMAGE`** (registry push **before** PR open). If publish is blocked, **do not** open a manifest PR substituting **`YOUR_GIT_SHA`** or empty creds -- hand off commands instead.
- **Checkout** **`AMD-SLAI/slai-app-dev`**, create a branch from **`dev`** or **`main`** to match the target environment (**[platform-context.md](references/platform-context.md)** § *Branches and URLs*).
- **Copy** the final **`deployment.yaml`**, **`service.yaml`**, and **`secrets.enc.yaml`** into **`deploy/apps/<app_id>/`** on that branch (you may have staged them under **`deploy/slai-app-dev/<app_id>/`** in the app repo first -- **`image:`** must already be the real **`FULL_IMAGE`** before this copy).
- **`git add` / `commit` / `push`** the branch; open the PR with **`gh pr create`** (if **`gh`** is authenticated) or instruct the user to open **Compare & pull request** on GitHub. PR title/body should name **`app_id`** and note **Harbor** tag / **Platform deploy** follow-up.
- If the agent **cannot** push (no **GitHub** credentials), output: branch name, file paths, and copy-paste **`git`** / **`gh`** commands.

### 5. Deploy

- After merge, trigger **Platform deploy (git + Harbor)** in **Actions** on **`AMD-SLAI/slai-app-dev`** with your **`app_id`**, from the branch that matches the target env (**`main`** vs **`dev`**). Optional: **`gh workflow run "Platform deploy (git + Harbor)" -f app_id=<app_id>`** if you have access.
- Applying manifests to the cluster is **platform automation** -- you only need to land a good PR.

## Examples

### Example A -- "I have a Node app in `my-frontend/`"

0. **§0e:** **`cp -n .env.example .env`**; obtain **`HARBOR_*`** from **slai-app-dev** maintainers -- if missing, **stop** with **"What you need to do next"** (no publish/PR in the same turn).
1. Add **Dockerfile** (multi-stage if needed), **`USER`**, **`EXPOSE`**, health route.
2. Add **`deploy/slai-app-dev/my-frontend/deployment.yaml`** + **`service.yaml`** from the skill templates (§1b); wire secrets / **OTEL** as needed (placeholder **`image:`** ok **only** until publish).
3. Produce **`secrets.enc.yaml`** from **`*.raw.yaml`** (§3).
4. **`publish-image-harbor.sh`** -> read **`.cache/harbor-last-image.env`** -> set **`deployment.yaml`** **`image:`** to **`FULL_IMAGE`**.
5. In **`slai-app-dev`**, branch + **`deploy/apps/my-frontend/`** with **stamped** **`deployment.yaml`**, **`service.yaml`**, and **`secrets.enc.yaml`**. Add **`networkpolicy.yaml`** when the pod needs **non-default egress** (DB, APIs, etc.) or to lock **ingress** to the cluster ingress controller -- see **[`references/network-egress.md`](references/network-egress.md)**.
6. In the **application** repo, add **`.github/workflows/deploy-prod.yml`** from **[`deploy-prod.yml.example`](assets/templates/deploy-prod.yml.example)** and document **§1c** secrets/variables for the team (**`SLAI_APP_DEV_PR_TOKEN`**, **`HARBOR_*`**, **`APP_ID`**, **`IMAGE_NAME`**, **`BUILD_CONTEXT`**).
7. PR (single app dir) -> merge -> **`app_id=my-frontend`** **Platform deploy**; later redeploys use **Deploy prod** (copies handoff manifests + Harbor image; §1c PAT + **Actions** secrets).

### Example B -- Dry validation before PR

From **`slai-app-dev`** repo root (or pass absolute path):

```bash
python3 skills/app-platform/scripts/main.py deploy/apps/hello-web
python3 skills/app-platform/scripts/main.py --strict deploy/apps/<app_id>
```

Exits non-zero if required files or **`image:`** are missing. **`--strict`** also requires **`networkpolicy.yaml`** and **OTEL** env in **`deployment.yaml`** (see **[references/platform-context.md](references/platform-context.md)** § *Observability*).

### Example C -- Ongoing release via **`Deploy prod`**

1. Ensure **§1c** **`deploy-prod.yml`** is committed in the **application** repo and **Actions** secrets/variables are set (if **`SLAI_APP_DEV_PR_TOKEN`** is missing, complete the **browser** PAT steps in **§1c** on the **application** repo).
2. Merge application changes on **`main`** (or the branch you run the workflow from).
3. Run **Actions -> Deploy prod -> Run workflow**; choose **`slai_base_ref`** (**`main`** vs **`dev`**) to match **[platform-context.md](references/platform-context.md)** § *Branches and URLs*.
4. Review and merge the **automated PR** on **`AMD-SLAI/slai-app-dev`** (handoff manifest sync + **`image:`** stamped to the new **`FULL_IMAGE`**).
5. Run **Platform deploy (git + Harbor)** on **`slai-app-dev`** for your **`app_id`** (§5).

## Markdown vs scripts (maintenance)

| Concern | Prefer | Optional script |
|--------|--------|-----------------|
| **`deployment.yaml` / `service.yaml`** | Skill **templates** + assistant-edited YAML (**§1b**) | -- |
| **Harbor build / publish scripts** | Copy from **`assets/templates/`** (**`build-image.sh.example`**, **`publish-image-harbor.sh.example`**) (**§1**) -- real **docker/podman** | -- |
| **`deploy-prod.yml`** | Copy **[`assets/templates/deploy-prod.yml.example`](assets/templates/deploy-prod.yml.example)** -> **`.github/workflows/deploy-prod.yml`** (**§1c**) | -- |
| **`.gitignore`** | **§0d** / **platform-context.md** -- merge lines by hand | -- |
| **SOPS encrypt** | **[sops-slai-app-dev-clone.md](references/sops-slai-app-dev-clone.md)** | **`encrypt-secrets-yaml.sh`** (Linux amd64; clone + sops bootstrap) |
| **Pre-PR validation** | -- | **`main.py`** (machine checks; CI-friendly) |

## Scripts

| Script | Purpose |
|--------|---------|
| **[scripts/main.py](scripts/main.py)** | **Validation** (not scaffolding): **`deploy/apps/<app>/`** has required files, **`image:`**, SOPS-shaped **`secrets.enc.yaml`**. Optional **`--strict`**: **`networkpolicy.yaml`** + **OTEL** env. |
| **[scripts/encrypt-secrets-yaml.sh](scripts/encrypt-secrets-yaml.sh)** | **Optional** SOPS helper for **Linux amd64**; canonical flow remains **[sops-slai-app-dev-clone.md](references/sops-slai-app-dev-clone.md)**. |

```bash
# From slai-app-dev repo root
python3 skills/app-platform/scripts/main.py deploy/apps/<app_id>
```

```bash
# Optional: Linux amd64 convenience (or follow sops-slai-app-dev-clone.md manually)
/path/to/skills/app-platform/scripts/encrypt-secrets-yaml.sh --app-id <app_id> --raw /path/to/secrets.raw.yaml
```

## References

- **[references/guidelines.md](references/guidelines.md)** -- conventions, anti-patterns, Podman/Pandora notes
- **[references/platform-links.md](references/platform-links.md)** -- canonical URLs and paths
- **[references/okta-oauth-web.md](references/okta-oauth-web.md)** -- Okta / OIDC for web apps on app-platform URLs
- **[references/otel-web-semconv.md](references/otel-web-semconv.md)** -- minimal HTTP OpenTelemetry semantic conventions
- **[references/network-egress.md](references/network-egress.md)** -- lock down egress; declare downstream ports (e.g. MySQL)
