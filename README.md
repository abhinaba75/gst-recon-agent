# Recon-Agent ⚡

> Autonomous, Multi-Agent GST Input Tax Credit (ITC) Reconciliation & Supplier Recovery Engine.

[![Built on AWS](https://img.shields.io/badge/Built%20on-AWS%20Bedrock-FF9900?logo=amazon-aws)](https://aws.amazon.com/bedrock/)
[![Framework](https://img.shields.io/badge/Agentic%20Framework-Strands%20SDK-0A84FF)](https://github.com/)
[![Compliance](<https://img.shields.io/badge/GST%20Compliance-Rule%2088D%20%7C%20Sec%2016(2)(aa)-10B981>)](#)
[![Hackathon](https://img.shields.io/badge/WeMakeDevs-AWS%20First%20Commit%202026-8B5CF6)](#)

---

## 🚀 Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python fixtures/generate_mock_data.py     # regenerate synthetic GST fixtures
streamlit run frontend/app.py             # → http://localhost:8501
```

The dashboard is fully self-contained: a bundled fallback engine drives the whole demo with
zero AWS dependencies. Click **⚡ Load Demo Fixtures** and go.

## 🖥️ Two surfaces, one engine

| Surface | Stack | What it is for |
|---|---|---|
| `web/` | React 19 + TypeScript + Vite 7 + Tailwind v4 + **shadcn/ui** | **The product site.** The dashboard shell from `dashboard-01` (sidebar, site header, section cards, chart, data table) and the sign-in page from `login-04`, wrapped around a getting-started guide, the four figures, the Excel-vs-agent comparison, the recovery list, the ledger, the activity log, the label glossary and an assistant that answers questions about any of them. Day/night themes, all 22 Eighth Schedule languages plus English, keyboard- and screen-reader-first. |
| `frontend/app.py` | Streamlit | **The compliance console.** Live uploads, the Bedrock toggle, and the operational dispatch path with its DynamoDB audit trail. |
| `api/main.py` | FastAPI | The one bridge: the web app calls `/api/dispatch`, which calls the same `backend/` modules the console uses — one implementation of every rule. |

The web app never invents a figure: it renders `web/src/data/snapshot.json`, exported from a real engine run.

```bash
# Re-export the snapshot after changing fixtures or engine behaviour
.venv/bin/python scripts/export_snapshot.py

# Web app with the API behind it (one port, /api proxied to :8000)
sh ./run_web.sh                     # → http://localhost:5173
cd web && bun run build             # static build → web/dist
```

With no API running the site still renders — and the dispatch dialog says plainly that nothing was sent. A fabricated “delivered” is the one outcome this product must never produce.

**Sign in** with the demo workspace: `demo@recon-agent.in` / `demo-88d`. Every credential is verified by the engine, not by the browser. Create an account on the deployment itself (stored in `.recon-users.json`, or in DynamoDB with `RECON_USERS_TABLE`; `RECON_ALLOW_SIGNUP=0` closes registration), or set `RECON_UI_EMAIL` and `RECON_UI_PASSWORD` to replace the demo pair — the page stops advertising the demo the moment you do.

**Social sign-in** appears one button at a time, and only for providers that are configured, because a button that cannot work is worse than none:

| Provider | Variables |
|---|---|
| Google | `RECON_GOOGLE_CLIENT_ID`, `RECON_GOOGLE_CLIENT_SECRET` |
| GitHub | `RECON_GITHUB_CLIENT_ID`, `RECON_GITHUB_CLIENT_SECRET` |
| Apple | `RECON_APPLE_CLIENT_ID` and either `RECON_APPLE_CLIENT_SECRET` or `RECON_APPLE_TEAM_ID` + `RECON_APPLE_KEY_ID` + `RECON_APPLE_KEY_PATH` (the `.p8` key) |
| **Clerk (hosted)** | `RECON_CLERK_ISSUER`, `RECON_CLERK_SECRET_KEY`, `RECON_CLERK_PUBLISHABLE_KEY` — accounts, email verification, password reset and every social connection are then managed in Clerk's dashboard, not in this code |

Register the callback `https://<your-host>/api/auth/<provider>/callback` with each provider. If your page is served by a proxy that rewrites `Host` (the bundled Vite dev server does), also set `RECON_ALLOWED_ORIGINS` to the address the page is actually on, for example `http://localhost:5173`.

**Clerk needs no callbacks to register.** Set the three variables above and the sign-in card renders Clerk's own hosted sign-up/sign-in flow: the publishable key is public by design, and the browser hands the session token it receives to `POST /api/auth/clerk`, which verifies it against Clerk's own signing keys (JWKS), the configured issuer and the allowed origins before any account is opened. Social connections, email verification, password reset and attack protection are all switches in Clerk's dashboard. The `iss` must be your Clerk Frontend API URL (`https://<app>.clerk.accounts.dev`), and origins beyond `http://localhost:5173` go in `RECON_CLERK_ALLOWED_ORIGINS`.

**Where the card appears.** A development Clerk instance only serves its hosted sign-in from localhost or an origin you allow-listed; from any other domain clerk-js fails its handshake and the provider can take the React tree down with it — a blank page. The sign-in page therefore mounts the card only where it can work (the engine's allowed origins, or localhost) and wraps it in an error boundary, so a Clerk failure can at worst hide the card, never the password form. On a remote preview domain without allow-listing you get the password form, sign-up, and skip entry — add your preview origin to `RECON_CLERK_ALLOWED_ORIGINS` to see the hosted card there.

## 📚 Documentation

**Everything is documented in [`DOCUMENTATION.md`](DOCUMENTATION.md)** — the domain problem,
fixtures (all four test groups with exact figures), both reconciliation engines (the Excel
VLOOKUP villain vs the semantic AI pipeline), the dashboard section by section, the WhatsApp
A2A recovery flow, the 30-check test suites, and the backend integration contract for the
AWS Bedrock / Strands orchestrator.

## ✅ Verify

```bash
.venv/bin/python tests/validate_fixtures.py   # data + pipeline assertions
.venv/bin/python tests/smoke_ui.py            # headless Streamlit UI assertions
.venv/bin/python tests/test_backend.py        # persistence, comms agent, parser, S3
.venv/bin/python tests/test_api.py            # the FastAPI surface and the assistant
cd web && bun run typecheck && bun run check:i18n && bun run smoke && bun run build
```
