# Okta / OAuth for web apps on the SLAI app platform

App-platform workloads use **plain OIDC/OAuth** -- **not** the MCP stack (**no DCR**, **no BFF**, **no DPoP** unless your security team requires it).

## Default pattern: confidential web client

**AMD Okta org:** **production** **`https://amdsso.okta.com`**; **development / preview** **`https://amdsso.oktapreview.com`**. Set **`OIDC_ISSUER`** (or equivalent) to your authorization server under that org, e.g. **`https://amdsso.okta.com/oauth2/<auth-server-id>`** (prod) or **`https://amdsso.oktapreview.com/oauth2/<auth-server-id>`** (preview) -- confirm **`auth-server-id`** with **Eng IT**.

1. Register a **Web** / **confidential** Okta application: **authorization code** (+ **refresh token** if needed), **client id** + **client secret**, **PKCE** as required by Okta policy.
2. **Redirect URIs** use your app's public host: **`https://<app_id>.app-platform.amd.com/...`** (prod) and **`https://<app_id>.app-platform-dev.amd.com/...`** (dev). See [**Branches and URLs** / **Ingress** in `platform-context.md`](platform-context.md#branches-and-urls); you still register **each** app's concrete URIs in Okta. More repo context: [`deploy/README.md`](../../../deploy/README.md).
3. Implement login with your framework's **OIDC middleware** (Spring, ASP.NET, Passport, etc.): exchange **code** for tokens server-side using the **client secret** (secret only on the server, never in the browser bundle).
4. **Do not** copy MCP **`okta_auth.py`**, **dynamic client registration**, or **BFF session token** patterns from **MCP-oriented stacks** -- those exist for AI clients on the MCP platform, not for standard web apps.

If your org automates Okta with **declarative YAML**, use a bundle shaped like **`okta_org`**, **`applications`** (each app's client settings), and **`redirect_uris`** lists. Keep entries **Web / confidential**, **authorization code** (+ **refresh token** if needed), and **static** redirect URIs on **`https://<app_id>.app-platform.amd.com/...`** and **`https://<app_id>.app-platform-dev.amd.com/...`**. **Do not** include MCP-only concepts (**DCR**, BFF-style callbacks, agent-only grants, or redirect patterns meant for non-browser clients).

**Example (illustrative -- adapt keys to your org's tooling):** [`../assets/templates/okta-registration.yaml.example`](../assets/templates/okta-registration.yaml.example).

## REST APIs behind the same (or another) deployment

If the product exposes a **REST API** (JSON over HTTP):

| Expectation | Notes |
|-------------|--------|
| **`Authorization: Bearer &lt;token&gt;`** | Accept an **Okta access token** (JWT) from callers. Validate **signature** (JWKS from issuer), **`iss`**, **`aud`** (your API's configured audience), **`exp`**, and scopes/claims per product policy. |
| **XAA (Cross-App Access)** | Callers may present a **Bearer access token** produced by Okta **token exchange** across apps / authorization servers. Validate it like any Okta JWT: **JWKS from `iss`**, **`aud` must match your resource authorization server's configured audience** (often `api://...`), **`exp`**, scopes/claims. **`iss`** is typically your **resource** custom authorization server issuer (`https://{okta-org}/oauth2/{auth-server-id}`), not the caller's. Admin setup uses **managed XAA connections** and **trusted authorization servers** on the target auth server -- coordinate with **security / Eng IT** for org-specific values. |

**No** requirement to implement MCP **`xaa_client.py`** or **`Mcp-Session-Id`** for a normal REST service -- those are MCP transport concerns. If you **call** other services with a user's delegated access, use **Okta** token exchange / **XAA** as configured by **security / Eng IT**, and validate downstream **Bearer** tokens like any Okta JWT (**§ XAA reference material** above).

### XAA reference material (protocol detail)

Okta's behavior differs from the IETF ID-JAG two-step draft in important ways (token types, single-step exchange on custom auth servers, `api_services` clients, trusted-server lists). Useful reads:

| Source | Use |
|--------|-----|
| [Okta -- Cross App Access (blog)](https://developer.okta.com/blog/2025/09/03/cross-app-access) | Product overview |
| [RFC 8693](https://www.rfc-editor.org/rfc/rfc8693) | Token exchange baseline |
| **Internal AMD XAA detail** | Program-specific POC docs and registration checklists from **security / Eng IT** (not stored in **`slai-app-dev`**). Public background: Okta blog + RFC 8693 in this table. |

## When onboarding: ask the app team

1. **Browser SSO (Okta)?** If no, skip this page for login (API keys etc. are separate).
2. **Confidential server-side login** vs **SPA** using **public** client + **PKCE** (browser) calling your API with **access tokens** -- pick one model; default recommendation for enterprise web is **confidential** server app or **BFF-less** SPA + API with **PKCE** public client, **not** MCP-style BFF.
3. **REST API** -- confirm **Okta audience** for the API and whether **XAA** exchanges apply; document **`aud`** and issuer URLs in the app repo.

## Secrets (SOPS)

Store **`client_secret`** (and any API client secrets) only in **`secrets.enc.yaml`**. Typical env names: **`OIDC_CLIENT_ID`**, **`OIDC_CLIENT_SECRET`**, **`OIDC_ISSUER`** (or Okta domain + authorization server path).

## Related

- **[`assets/templates/okta-registration.yaml.example`](../assets/templates/okta-registration.yaml.example)** -- admin / Okta-as-code handoff template (not deployed by Platform deploy)
- **[`platform-context.md`](platform-context.md)** -- URLs, SOPS, OTel
