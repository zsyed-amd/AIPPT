# app-platform -- guidelines for app developers

## Prerequisites

- **Clone** **`AMD-SLAI/slai-app-dev`** to open PRs under **`deploy/apps/<app_id>/`** (sparse checkout is fine if policy allows).
- **Application source** stays in the **app's repo**; **`slai-app-dev`** only gets **Kubernetes YAML** + **SOPS ciphertext**.
- **URLs, branches, OTel, SOPS basics:** **[references/platform-context.md](platform-context.md)**.
- **Platform deploy / Actions UI:** repo root **`docs/platform-deploy-github-actions.md`** if you need step-by-step.

## Do

- Ask early if the app needs **Okta / OIDC**; if yes, follow **[references/okta-oauth-web.md](okta-oauth-web.md)** (confidential web client; REST APIs validate **Bearer** tokens).
- Add **`networkpolicy.yaml`** when the pod talks to **MySQL**, internal **HTTPS**, etc. -- default allow is **DNS + OTLP :4317** only; see **[references/network-egress.md](network-egress.md)** and **[networkpolicy.yaml.example](../assets/templates/networkpolicy.yaml.example)**.
- Set **OTel** env from **[references/platform-context.md](platform-context.md)** § *OpenTelemetry*; use **[references/otel-web-semconv.md](otel-web-semconv.md)** for minimal HTTP attributes.
- Use **immutable** image tags (**full git SHA**) in **`deployment.yaml`** after Harbor publish.
- **Need a Harbor robot?** Open an **Issue** on **`AMD-SLAI/slai-app-dev`** (or program intake) -- see **[references/platform-context.md](platform-context.md)** § *Harbor credentials*.
- Add **`.github/workflows/deploy-prod.yml`** from **[`deploy-prod.yml.example`](../assets/templates/deploy-prod.yml.example)** on **greenfield** app repos (**`SKILL.md`** §**1c**) so **Actions -> Deploy prod** rebuilds, pushes Harbor, and opens a PR that **syncs** committed handoff YAML (**`deploy/slai-app-dev/<app_id>/`**) into **`deploy/apps/<app_id>/`** plus the new **`image:`**.
- Match **Service `selector`** to **Pod** labels in **Deployment**.
- **Plaintext secrets** only in **`*.raw.yaml`** (gitignored). Commit SOPS **`secrets.enc.yaml`** under **`deploy/slai-app-dev/<app_id>/`** using the **`.gitignore`** exception in **SKILL.md** §0d so CI can copy it.
- **One** **`deploy/apps/<app_id>/`** per PR unless platform **CI** requires splitting.
- **Harden** where possible: **`runAsNonRoot`**, **`runAsUser`/`runAsGroup`/`fsGroup` 65534**, **`seccompProfile: RuntimeDefault`**, **`readOnlyRootFilesystem`**, **`capabilities.drop: ["ALL"]`**, **`emptyDir`** for **`/tmp`** -- see **[deployment.yaml.example](../assets/templates/deployment.yaml.example)**.

## Container hardening

Canonical pattern: **[deployment.yaml.example](../assets/templates/deployment.yaml.example)**. Pair with **[networkpolicy.yaml.example](../assets/templates/networkpolicy.yaml.example)** if you need egress rules.

### Dockerfile (Python / **uv**)

- **Preferred in image:** **`chown -R 65534:65534 /app`** then **`USER 65534:65534`** (or **`COPY --chown=65534:65534`**) so the runtime user can read the app -- *when the build engine supports it*.
- **`UV_NO_CACHE=1`** avoids **`uv`** writing under **`$HOME/.cache`** on read-only / **`/tmp`**-only pods. Prefer **`CMD ["/app/.venv/bin/python", ...]`** instead of **`uv run`** at startup.

### Podman / overlay and Dockerfile ownership

On some **Podman** workstations (NFS roots, certain **overlay** storage configs), **`RUN chown ... 65534`** and **`COPY --chown=65534:65534`** fail with **`invalid argument`** or **`lchown ... invalid argument`** during **`podman build`**. **Mitigation:** omit **`USER`** and any **`chown` / `--chown`** in the **`Dockerfile`**; keep app code and static assets **world-readable**; rely on **`deployment.yaml`** **`securityContext`** (**`runAsUser`**, **`runAsGroup`**, **`fsGroup` `65534`**, **`runAsNonRoot`**) so the **pod** still runs non-root. The image may list **`root`** as default user; Kubernetes overrides the process UID.

## Avoid

- Committing **Harbor passwords**, **kubeconfig**, **plaintext** **`Secret`** YAML, or **age private keys**.
- **`:latest`** for production-like deploys if you care about rollback.
## Podman / Pandora (workstations)

If **`podman`** fails with **runc not found**, use **`podman --runtime /tool/pandora/.package/runc-*/bin/runc`** for **login**, **build**, **push**. Rootless **`podman build`** may need **`--storage-opt overlay.ignore_chown_errors=true`**. The skill's **`publish-image-harbor.sh.example`** already selects Docker when usable and otherwise uses this Podman + temp-root pattern -- **copy that template**, do not ship a docker-only publish script. Harbor login and cache tips: **[references/platform-context.md](platform-context.md)** § *Workstation*.

## Markdown-first vs bundled scripts

- **Kubernetes YAML:** Author from **[deployment.yaml.example](../assets/templates/deployment.yaml.example)** and **[service.yaml.example](../assets/templates/service.yaml.example)** in the skill -- no scaffolding scripts.
- **Harbor build/publish:** Not replaceable by markdown -- copy **[build-image.sh.example](../assets/templates/build-image.sh.example)**, **[publish-image-harbor.sh.example](../assets/templates/publish-image-harbor.sh.example)**, and **[dot-env.harbor.example](../assets/templates/dot-env.harbor.example)** into the app repo (**§1** in **SKILL.md**). **`slai-app-dev`** root **`scripts/`** should stay in sync with those templates when behavior changes.
- **`.gitignore` (app repo):** Merge **`*.raw.yaml`**, **`.env`**, **`*.enc.yaml`**, and **`!deploy/slai-app-dev/**/secrets.enc.yaml`** (see **SKILL.md** §0d and **[platform-context.md](platform-context.md)**).
- **SOPS:** Canonical procedure **[sops-slai-app-dev-clone.md](sops-slai-app-dev-clone.md)**. **[encrypt-secrets-yaml.sh](../scripts/encrypt-secrets-yaml.sh)** is an optional **Linux amd64** shortcut.
- **`main.py`:** Pre-PR / CI validation only -- keep it for automated checks, not for generating manifests.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| **`docker: command not found`** when running **`publish-image-harbor.sh`** | Expected on some hosts -- ensure your app copy of **publish-image-harbor** under **`scripts/`** matches **[`publish-image-harbor.sh.example`](../assets/templates/publish-image-harbor.sh.example)** (Podman fallback), or install a working Docker CLI. |
| **Harbor login: invalid username/password** | Robot secret typo, expired robot, or wrong registry project -- re-copy **`HARBOR_USERNAME`** / **`HARBOR_PASSWORD`** into **`.env`** from maintainers. |
| **`chown` / `COPY --chown` fails during `podman build`** | See § *Podman / overlay and Dockerfile ownership* above; drop image-level **`USER`**/**`chown`**, keep **`deployment.yaml`** **`runAsUser` 65534`. |
| **ImagePullBackOff** | **`image:`** tag exists in Harbor; visibility / pull policy -- ask platform if unsure. |
| **SOPS encrypt fails** | You have the **public** age recipient from **`.sops.yaml`**; use **`sops -e`**. Decrypt problems on **merge/deploy** -> platform / **`.sops.yaml`** alignment. |
| **PR path guard failed** | One **`deploy/apps/<id>/`** per PR unless platform **CI** allows combined PRs. |
| **Deploy didn't run** | Someone with rights must run **Platform deploy**; see **`docs/platform-deploy-github-actions.md`**. |
