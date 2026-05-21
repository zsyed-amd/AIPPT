# app-platform

**app-platform** is a Cursor Agent Skill for developers who **containerize** applications and ship them through **AMD-SLAI `slai-app-dev`**: **Harbor** (**`hw-slai-dev`**), **git-backed** Kubernetes manifests under **`deploy/apps/<app_id>/`**, **SOPS + age** for secrets, and **GitHub Actions** Platform deploy.

## Key capabilities

- **Dockerfile** guidance for **restricted** RKE2 namespaces (**linux/amd64**, non-root, probes).
- **Harbor gate:** copy **`.env.example`** to **`.env`**, require **`HARBOR_*`** in **`.env`**; if missing, **stop** with **next steps** (no publish or platform PR in the same turn).
- **Publish** using **build-image** / **publish-image-harbor** scripts copied from **`assets/templates/`** (see **`.example`** files there; Docker or Podman); credentials only from env or CI.
- **Workstation** notes in **`references/guidelines.md`** (Harbor auth, missing **docker**, Podman **`chown`** issues).
- **Manifest trio:** **`deployment.yaml`**, **`service.yaml`**, **`secrets.enc.yaml`**; app-repo handoff under **`deploy/slai-app-dev/<app_id>/`**.
- **`Deploy prod`** (template **`deploy-prod.yml.example`**): **`workflow_dispatch`**: rebuild, Harbor push, PR on **`slai-app-dev`** that copies handoff into **`deploy/apps/<app_id>/`** and stamps **`image:`**. PAT + Actions secrets documented in **SKILL.md**.
- **PR scope:** one **`deploy/apps/<app_id>/`** per PR unless **`platform-infra`** / maintainers say otherwise.
- **Hub:** **`references/platform-context.md`** for URLs, OTel, SOPS basics, Harbor via Issues.

## Use cases

- Onboard a **new** service or SPA on the SLAI cluster.
- Review **Dockerfile** and **Service** against platform rules before a PR.
- Let an agent handle layout, **`gh`** workflow dispatch, and SOPS command reminders.

## Requirements

- Access to **`github.com/AMD-SLAI/slai-app-dev`** (clone + PR).
- **Harbor** push credentials on the host that publishes, or a path to request them (Issues).
- **`sops`** and **`age`** when encrypting secrets locally (or use a devcontainer with tools).
- **`Deploy prod`:** **`gh`** on runners and egress to Harbor.

This skill **does not** replace **code review**, **security sign-off**, or **platform** approval.
