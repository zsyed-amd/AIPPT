# Index -- files in this skill

| File | Purpose |
|------|---------|
| [platform-context.md](platform-context.md) | Repo paths, URLs, OTel, SOPS basics, Harbor Issues |
| [sops-slai-app-dev-clone.md](sops-slai-app-dev-clone.md) | Clone `slai-app-dev` for `.sops.yaml`; encrypt from `/tmp/$USER` |
| [guidelines.md](guidelines.md) | Conventions, Podman, troubleshooting |
| [okta-oauth-web.md](okta-oauth-web.md) | Okta / OIDC / XAA |
| [otel-web-semconv.md](otel-web-semconv.md) | Minimal HTTP OTel conventions |
| [network-egress.md](network-egress.md) | NetworkPolicy egress |
| [../assets/templates/deployment.yaml.example](../assets/templates/deployment.yaml.example) | Deployment template |
| [../assets/templates/service.yaml.example](../assets/templates/service.yaml.example) | Service template |
| [../assets/templates/build-image.sh.example](../assets/templates/build-image.sh.example) | Harbor local build script template |
| [../assets/templates/publish-image-harbor.sh.example](../assets/templates/publish-image-harbor.sh.example) | Harbor publish + `.cache/harbor-last-image.env` template |
| [../assets/templates/deploy-prod.yml.example](../assets/templates/deploy-prod.yml.example) | App repo **Deploy prod**: rebuild -> Harbor -> sync handoff YAML into `deploy/apps/<id>/` -> PR |
| [../assets/templates/dot-env.harbor.example](../assets/templates/dot-env.harbor.example) | `.env.example` for Harbor variables |
| [../assets/templates/networkpolicy.yaml.example](../assets/templates/networkpolicy.yaml.example) | NetworkPolicy template |
| [../assets/templates/okta-registration.yaml.example](../assets/templates/okta-registration.yaml.example) | Okta admin YAML shape |
| [../scripts/main.py](../scripts/main.py) | Manifest validator |
| [../scripts/encrypt-secrets-yaml.sh](../scripts/encrypt-secrets-yaml.sh) | Optional **Linux amd64** SOPS helper (canonical flow: **sops-slai-app-dev-clone.md**) |

Platform-only topics: repo **`specs/`**, **`docs/`**.
