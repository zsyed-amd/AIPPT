# Egress lockdown and downstream dependencies

## Whitelist-only default (app-platform)

**Egress is a whitelist, not a blacklist.** For pods selected by this **`NetworkPolicy`**, **only** the **`egress`** rules in the manifest are allowed. **Every** non-standard destination and **port** must appear as its own rule.

| Category | Included by default? |
|----------|----------------------|
| **Cluster DNS** | **Yes** -- **kube-system**, **UDP/TCP 53** (verify labels in your cluster). |
| **OpenTelemetry OTLP** | **Yes** -- **TCP 4317** only, aligned with **`http://atlvslaiapp03:4317`** ([**OpenTelemetry** in `platform-context.md`](platform-context.md#opentelemetry-set-in-your-deployment)). Template uses a **port-only** egress rule (pods resolve **`atlvslaiapp03`** via cluster DNS). Optional: replace with a narrow **`ipBlock`** if Eng IT publishes a fixed collector CIDR. |
| **MySQL, Postgres, Redis, arbitrary HTTPS, LDAP, ...** | **No** -- **you must add** an explicit **`egress`** stanza per dependency (**port** + **`namespaceSelector`/`podSelector`** or **`ipBlock`**). |
| **Harbor / image registry** | **N/A** -- pulls are **kubelet/node**, not pod egress. |

Do **not** widen egress with **`0.0.0.0/0`** except where **Eng IT** documents an unavoidable pattern; prefer **per-service CIDR** or in-cluster **`podSelector`**.

## Principle

When the web app talks to **MySQL**, **internal REST APIs**, etc., **declare the destination and port** in **`deploy/apps/<app_id>/networkpolicy.yaml`**.

## North-south

**Ingress** is similarly scoped: allow only the **ingress controller** namespace -> **app container port** (adjust namespace label for your cluster).

## Workflow for agents

1. Ask: *Does the app call **MySQL**, **other databases**, or **specific TCP/UDP services** from inside the pod?*
2. For **each** dependency, add a **separate** **`egress`** rule with the **exact port** (e.g. **3306**). If **none**, the pod still only has **DNS + OTLP :4317** egress (collector URL in [**platform-context.md**](platform-context.md#opentelemetry-set-in-your-deployment)).
3. If OTLP or probes fail, confirm **DNS** resolves **`atlvslaiapp03`** (or the FQDN platform gave you), optionally narrow OTLP with **`ipBlock`**, or adjust **ingress** -- ask platform or see repo **`deploy/README.md`** / **`docs/`** for ingress/DNS detail.

## Template

- **[`assets/templates/networkpolicy.yaml.example`](../assets/templates/networkpolicy.yaml.example)**
