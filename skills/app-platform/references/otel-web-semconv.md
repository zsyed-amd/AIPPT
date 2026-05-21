# Minimal OpenTelemetry semantic conventions for web apps

**Goal:** Traces and metrics that behave well in **Tempo / Grafana** without hand-rolling uncommon attributes.

## Prefer auto-instrumentation

Use the **official** OpenTelemetry **auto-instrumentation** for your stack whenever possible (it emits **stable HTTP semantic conventions** correctly):

- **Java:** OpenTelemetry Java agent
- **.NET:** **`OpenTelemetry.Instrumentation.AspNetCore`**, **`HttpClient`**
- **Node.js:** **`@opentelemetry/auto-instrumentations-node`** (or framework packages)
- **Python:** **`opentelemetry-instrumentation-flask`**, **FastAPI**, **Django**, etc.

Auto-instrumentation implements the specs linked below; you mainly set **exporter** and **resource** env vars.

## Stable HTTP spans (reference)

Official docs: **[HTTP spans](https://opentelemetry.io/docs/specs/semconv/http/http-spans/)** (OpenTelemetry **semantic conventions**).

**Span names (low cardinality):** use **`{http.request.method} {http.route}`** where **`http.route`** is the parameterized route template (e.g. **`GET /users/{id}`**), not raw URLs with IDs.

**Commonly expected attributes** on server spans (many set automatically):

| Attribute | Notes |
|-----------|--------|
| **`http.request.method`** | **`GET`**, **`POST`**, ... |
| **`http.response.status_code`** | Integer |
| **`http.route`** | Template, e.g. **`/api/items/{item_id}`** |
| **`url.scheme`** | **`http`** / **`https`** |
| **`server.address`** / **`server.port`** | Host/port the server received |
| **`user_agent.original`** | Optional |

**Client calls** (outbound HTTP): see the same spec's **HTTP client** section; auto-instrumentation usually covers **`http.client.request.duration`** metrics and span links.

## Service identity (resource)

Set at process start (Kubernetes **`Deployment` `env`**):

- **`OTEL_SERVICE_NAME`** -- logical service name (often same as **`app_id`**).
- **`OTEL_RESOURCE_ATTRIBUTES`** -- optional: **`service.namespace=slai-app-platform`**, **`deployment.environment=production`** (or **`development`**).

Platform defaults for **`OTEL_EXPORTER_OTLP_ENDPOINT`** and gRPC **4317**: **[`platform-context.md`](platform-context.md)** § *OpenTelemetry*.

## What you usually **do not** need for a plain web app

- **MCP / GenAI** attributes (`mcp.*`, `gen_ai.*`) -- only if you expose MCP or LLM HTTP APIs; define spans using the same **OpenTelemetry semantic conventions** project as the HTTP links above (vendor-neutral **`opentelemetry.io`** specs).

## Logs

Prefer **OTLP logs** or **structured stdout** per org collector guidance (coordinate with platform if unsure). Correlate with traces using **`trace_id`** / **`span_id`** in log fields when the SDK supports it.

## Further reading

- [OpenTelemetry general attributes](https://opentelemetry.io/docs/specs/semconv/general/attributes/)
- [Trace context propagation (W3C)](https://www.w3.org/TR/trace-context/) -- ensure ingress/proxies preserve **`traceparent`** if you need end-to-end traces through gateways (platform-specific).
