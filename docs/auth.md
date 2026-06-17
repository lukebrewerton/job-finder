# Authentication

Job Finder uses **OIDC (OpenID Connect)** as a relying party. It does not implement its own user database or password flow — it delegates authentication entirely to whichever OIDC provider you configure. Any provider that supports the OIDC Discovery standard works: Google, Authentik, Keycloak, Dex, Okta, Auth0, and so on.

On first sign-in a user record is created automatically. Access can be restricted to a specific list of email addresses (see below).

---

## Environment variables

| Variable | Description |
|---|---|
| `OIDC_ISSUER` | The provider's issuer URL. Discovery metadata is fetched from `<issuer>/.well-known/openid-configuration`. |
| `OIDC_CLIENT_ID` | The client ID registered with the provider. |
| `OIDC_CLIENT_SECRET` | The client secret issued by the provider. |
| `OIDC_REDIRECT_URI` | The callback URL the provider redirects to after login. Must match exactly what is registered. |
| `OIDC_ALLOWED_EMAILS` | Comma-separated list of permitted email addresses. Leave blank to allow any authenticated identity (useful when the provider already restricts access). |
| `SESSION_SECRET` | Random string used to sign session JWTs. Generate with `openssl rand -hex 32`. Must be set and kept secret. |

---

## Google (simplest for personal use)

Google's OIDC issuer is free and requires no self-hosted infrastructure.

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → **APIs & Services** → **Credentials**.
2. Create an **OAuth 2.0 Client ID** (application type: Web application).
3. Add your redirect URI under **Authorised redirect URIs**:
   - Dev: `http://localhost:5173/api/auth/callback`
   - Prod: `https://jobs.yourdomain.com/api/auth/callback`
4. Copy the Client ID and Client Secret.

```
OIDC_ISSUER=https://accounts.google.com
OIDC_CLIENT_ID=123456789-abc.apps.googleusercontent.com
OIDC_CLIENT_SECRET=GOCSPX-your-secret
OIDC_REDIRECT_URI=https://jobs.yourdomain.com/api/auth/callback
OIDC_ALLOWED_EMAILS=you@gmail.com
SESSION_SECRET=<openssl rand -hex 32>
```

Set `OIDC_ALLOWED_EMAILS` to your own address — Google will authenticate anyone with a Google account otherwise.

---

## Authentik (self-hosted identity provider)

[Authentik](https://goauthentik.io) is a self-hosted identity platform well-suited to homelab stacks. If you already run Authentik as part of a Traefik-fronted setup this is the recommended option — it gives you SSO with your other services and centralised access control.

### Create a provider

1. In Authentik admin → **Applications** → **Providers** → **Create** → **OAuth2/OpenID Provider**.
2. Set **Name** to `job-finder`.
3. **Authorization flow**: your default authorisation flow (e.g. `default-authentication-flow`).
4. **Client type**: Confidential.
5. **Redirect URIs**: `https://jobs.yourdomain.com/api/auth/callback`
6. Copy the **Client ID** and **Client Secret** from the provider detail page.

### Create an application

1. **Applications** → **Applications** → **Create**.
2. Set **Name** to `Job Finder`, **Slug** to `job-finder`.
3. Link it to the provider you just created.
4. Optionally bind a **Policy** to restrict which Authentik users can access the app.

### Environment variables

```
OIDC_ISSUER=https://auth.yourdomain.com/application/o/job-finder/
OIDC_CLIENT_ID=<from provider page>
OIDC_CLIENT_SECRET=<from provider page>
OIDC_REDIRECT_URI=https://jobs.yourdomain.com/api/auth/callback
OIDC_ALLOWED_EMAILS=
SESSION_SECRET=<openssl rand -hex 32>
```

The issuer URL ends with the application slug. Authentik exposes the discovery document at `<issuer>/.well-known/openid-configuration` — verify it loads before deploying.

Because Authentik already enforces which users can access the application, `OIDC_ALLOWED_EMAILS` can be left blank. Use it as an extra layer if you want the app itself to enforce an allowlist independent of the provider.

---

## Restricting access with `OIDC_ALLOWED_EMAILS`

```
OIDC_ALLOWED_EMAILS=alice@example.com,bob@example.com
```

Set to a comma-separated list of addresses. Any authenticated user whose email is not in the list receives a 403 at the callback step — they never reach the app. Leave blank to allow all identities the provider approves.

Multi-tenant note: each user gets their own triage state, CV, and search profile. Adding a second user requires no code changes — they just sign in.
