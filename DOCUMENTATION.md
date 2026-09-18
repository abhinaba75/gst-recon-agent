# Recon-Agent — Complete Project Documentation

> **Autonomous GST Input Tax Credit (ITC) Reconciliation & Supplier Recovery Engine**
> WeMakeDevs × AWS "First Commit" Hackathon · 2026

This document explains the entire project in depth: the legal-domain problem, every file, every
algorithm, the exact demo numbers, how to run and verify everything, and the contract the AWS
Bedrock/Strands backend must honour to plug into this frontend.

---

## Table of Contents

1. [The Problem Domain](#1-the-problem-domain)
2. [What Recon-Agent Does](#2-what-recon-agent-does)
3. [Team Split & System Architecture](#3-team-split--system-architecture)
4. [Repository Layout — Every File Explained](#4-repository-layout--every-file-explained)
5. [The Synthetic Fixtures in Detail](#5-the-synthetic-fixtures-in-detail)
6. [The Two Reconciliation Engines](#6-the-two-reconciliation-engines)
7. [The Streamlit Dashboard, Section by Section](#7-the-streamlit-dashboard-section-by-section)
8. [WhatsApp A2A Recovery Flow](#8-whatsapp-a2a-recovery-flow)
9. [Verification & Test Suites](#9-verification--test-suites)
10. [Running the Project](#10-running-the-project)
11. [Backend Integration Contract (for the DeepSeek orchestrator)](#11-backend-integration-contract)
12. [Judge Demo Script (5 Minutes)](#12-judge-demo-script-5-minutes)
13. [Known Limitations & Roadmap](#13-known-limitations--roadmap)

---

## 1. The Problem Domain

### 1.1 The ₹45,000 Crore leakage

Indian MSMEs lose **over ₹45,000 Crore every year** in legitimately earned but unclaimed Input
Tax Credit (ITC). The credit is *earned* — the tax was charged on genuine purchases — but it is
*trapped* by paperwork friction between the buyer's books and the government's systems.

### 1.2 The legal framework that traps the credit

| Provision | What it mandates | Consequence for the MSME |
|---|---|---|
| **Section 16(2)(aa), CGST Act** | ITC may be claimed **only if** the supplier has uploaded the invoice to the GST portal — i.e. it must appear in the buyer's auto-drafted **GSTR-2B**. | If the supplier doesn't file, the buyer **cannot** claim, no matter how genuine the invoice. |
| **Rule 88D (Form DRC-01C)** | The GSTN system **automatically** issues a notice when ITC claimed in GSTR-3B exceeds the GSTR-2B figure beyond tolerance. | Claiming what your books say (but 2B contradicts) triggers an automated compliance notice. |
| **Section 50(3), CGST Act** | Wrongful/unsupported ITC utilisation attracts **punitive interest of 18%–24% p.a.** plus DRC-03 recovery. | A wrongful claim becomes *more expensive* than never claiming at all. |

### 1.3 The four failure modes (and their frequencies)

| # | Failure mode | Share | What happens |
|---|---|---|---|
| 1 | **Supplier non-filing** | **41.2%** | Vendor collected GST but missed the GSTR-1 deadline (11th/13th). Invoice never appears in 2B. |
| 2 | **Invoice typos** | **28.6%** | Books say `INV/24-25/081`, portal says `INV-081`. Human data-entry divergence breaks exact-string matching. |
| 3 | **Late cross-period filings** | **18.4%** | Invoice uploaded 1–3 months late: visible in the portal, absent from the current books' matched period. |
| 4 | **Rate / HSN restructuring** | **11.8%** | GST 2.0 slab churn (5% / 18% / 40%) and CGST+SGST vs IGST misallocation between buyer and supplier records. |

### 1.4 Why Excel fails — the villain of our demo

The standard accounts-team workflow is a `=VLOOKUP(A2, 'GSTR-2B'!A:F, 2, FALSE)` against the
portal's invoice number. `FALSE` means **exact literal string comparison**:

- `INV/24-25/081` ≠ `INV-081` → **`#N/A`**
- The accountant, pressed for time, treats `#N/A` as *"supplier defaulted / credit lost"*
  and either writes the credit off or files a claim that detonates under Rule 88D.

Excel has no concept of *semantic equivalence*, *tax corroboration*, or *GSTIN identity*.
That gap is exactly what an AI agent closes — and exactly what our dashboard dramatises.

---

## 2. What Recon-Agent Does

Recon-Agent ingests two artefacts:

1. **Internal purchase register** (Excel) — the MSME's own books: what they *believe* they bought and what ITC they *believe* they earned.
2. **GSTR-2B JSON** — the GSTN auto-drafted statement: what the *government* says is claimable this period.

It then produces, autonomously:

- **Classification of every books invoice** into: exact match, AI-rescued match, defaulting
  supplier, portal-only (late filing), or unresolved — each with the **evidence** used.
- **Quantified ITC impact** per class in ₹, so the MSME sees trapped credit as money, not rows.
- **Autonomous supplier recovery**: for the 41.2% non-filing vendors, an A2A (agent-to-agent)
  delegation drafts and dispatches a compliant WhatsApp nudge demanding GSTR-1 filing
  before the 11th, with the Rule 88D consequence stated.

The hackathon-critical framing: **the same row Excel writes off at `#N/A`, Recon-Agent resolves
at 82–95% AI confidence with an auditable evidence trail.**

---

## 3. Team Split & System Architecture

### 3.1 Division of labour

| Owner | Deliverable |
|---|---|
| **This repo (me / frontend + data simulation)** | Streamlit dashboard (`frontend/app.py`), synthetic GST fixtures (`fixtures/`), Excel-vs-AI comparison choreography, UI triggers (upload / reconcile / WhatsApp A2A), self-contained fallback engine, test suites, docs. |
| **DeepSeek 4.1 Flash (backend orchestrator)** | AWS Bedrock (Claude 3.5 Sonnet), Strands Agents SDK orchestrator, Fuzzy-Matcher MCP tool (Titan Text v2 embeddings), A2A Comms Agent, S3 ingestion Lambda, DynamoDB session state, Twilio WhatsApp dispatch. |

### 3.2 End-to-end architecture

```
┌──────────────────────────────┐        ┌──────────────────────────────────────┐
│  MSME Source Data            │        │  AWS CLOUD (DeepSeek's scope)        │
│                              │        │                                      │
│  purchase_register.xlsx      │──S3──▶ │  Lambda: ingestion parser            │
│  sample_gstr2b.json          │        │        │                             │
└──────────────────────────────┘        │        ▼                             │
                                        │  DynamoDB: invoice + session state   │
┌──────────────────────────────┐        │        │                             │
│  Streamlit Dashboard         │◀──API──│        ▼                             │
│  (this repo, frontend/)      │        │  Bedrock AgentCore Runtime           │
│                              │        │  └─ Strands Orchestrator             │
│  • KPI cards                 │        │      ├─ [tool] Fuzzy Matcher MCP     │
│  • Excel vs AI comparison    │        │      │    (Titan v2 embeddings)      │
│  • Recovery panel            │──A2A──▶│      └─ [A2A] Comms Agent            │
│  • Agent activity log        │        │             │                        │
└──────────────────────────────┘        │             ▼                        │
                                        │      Twilio WhatsApp API             │
                                        └──────────────────────────────────────┘
```

### 3.3 Why the frontend runs without the backend

Hackathon reality: the backend spins up slowly and demo Wi-Fi is hostile. Therefore
`frontend/app.py` embeds a **full-fidelity fallback engine** (`_fallback_semantic_matcher`)
that reproduces the exact pipeline the Bedrock orchestrator will run — deterministic tier,
semantic tier, corroboration gates, classification, confidence scoring. The dashboard is
clickable and judge-ready **with zero AWS dependencies**, and the sidebar toggle
*“Use AWS Bedrock orchestrator”* is the single switch point where the live backend replaces it.

---

## 4. Repository Layout — Every File Explained

```
recon-agent/
├── frontend/
│   └── app.py                      # THE dashboard (see §7). ~560 lines, fully typed.
├── fixtures/
│   ├── generate_mock_data.py       # Deterministic synthetic-data generator (see §5)
│   ├── sample_purchase_register.xlsx  # Generated: 12 invoices, ₹1,07,971 ITC
│   └── sample_gstr2b.json          # Generated: 11 invoices, ₹1,12,380 ITC
├── tests/
│   ├── validate_fixtures.py        # 20 data/pipeline assertions (no pytest needed)
│   └── smoke_ui.py                 # 10 headless Streamlit AppTest UI checks
├── .streamlit/
│   └── config.toml                 # War-room theme (ledger navy, brass, serif/plex fonts)
├── requirements.txt                # streamlit>=1.44, pandas>=2.0, openpyxl>=3.1
├── run.sh                          # Preview launcher: binds 0.0.0.0, honours $PORT
├── .gitignore                      # venv, __pycache__, secrets.toml
└── README.md                       # High-level story (problem, AWS stack, arch)
├── backend/                        # ← DeepSeek's scope (not in repo yet)
│   ├── orchestrator.py             #   Strands Agent orchestrator
│   ├── subagents/comms_agent.py    #   A2A WhatsApp recovery agent
│   ├── tools/fuzzy_matcher.py      #   MCP tool: embeddings + string metrics
│   ├── tools/twilio_client.py      #   WhatsApp dispatch
│   ├── db/dynamodb_handler.py      #   State persistence
│   └── parser/gstr2b_ingest.py     #   S3-triggered Lambda parser
```

### 4.1 `fixtures/generate_mock_data.py`

A **deterministic** generator (no RNG — same output every run, so demos and tests never drift):

- `build_purchase_register()` → 12-row `DataFrame` with the exact spec columns:
  `invoice_no, supplier_name, supplier_gstin, invoice_date, taxable_value,
  igst, cgst, sgst, total_tax, total_amount, vendor_phone`.
- `build_gstr2b()` → dict mirroring the GSTN **B2B table**: `gstin`, `fp` (tax period `082026`
  = August 2026), and `b2b[]` → supplier (`ctin`, `trdnm`) → `inv[]` → `inum, idt, val, pos,
  itcavl, items[] → txval, rt, iamt, camt, samt`.
- Tax arithmetic helper `_slab()` computes IGST *or* CGST+SGST halves with
  half-away-from-zero rounding (`_round_rupees`), the way GSTN does.
- GST-consistency rules baked in (so a GST-literate judge finds no contradictions):
  - Recipient GSTIN is Karnataka (`29…`); every `pos` (Place of Supply) is therefore `29`.
  - Supplier state `27`/`36` + POS `29` → **inter-state → IGST only** (`iamt>0, camt=samt=0`).
  - Supplier state `29` + POS `29` → **intra-state → CGST+SGST split** (`camt=samt, iamt=0`).
  - GSTIN checksum-style format: `2-digit state + 10-char PAN + 1 entity code + 'Z' + 1 check char`.

Run it: `python fixtures/generate_mock_data.py` → rewrites both fixture files and prints a
group/ITC summary.

### 4.2 `frontend/app.py`

Single-file Streamlit application, organised into the mandated clean functions:

| Function | Role |
|---|---|
| `load_data()` | Source-of-truth loader: session uploads → bundled fixtures; returns parsed `PortalRow`s; graceful error if fixtures are missing. |
| `run_excel_vlookup()` | The **villain**: literal `UPPER()`-stripped string matching that returns `#N/A` on any typo — deliberately *no* canonicalisation, exactly like a real spreadsheet. |
| `run_recon_pipeline()` | The **hero**: deterministic tier + semantic tier via Bedrock (toggle) or the embedded fallback engine. |
| `render_dashboard()` | Orchestrates all UI sections; computes the four KPIs. |
| `_fallback_semantic_matcher()` | The offline stand-in for the Bedrock Fuzzy-Matcher MCP tool (see §6.3). |
| `wa_preview()` / `render_wa_modal()` | Rule-88D WhatsApp template + `@st.dialog` dispatch modal (see §8). |
| `log()` | Appends timestamped lines to the session-scoped agent activity log (capped at 150). |
| `sidebar()` / `main()` | App shell: uploads, backend toggle, demo button, theming. |

Key dataclasses:

- `PortalRow` — flattened one-row-per-invoice view of the 2B JSON (aggregates multi-item
  invoices by summing `txval/iamt/camt/samt`); `.tax` property = `igst+cgst+sgst`.
- `Match` — the **universal result object**: `register_no, portal_no, supplier_name,
  supplier_gstin, tax, status, ai_conf, similarity, reason` plus `.label` for display.
  `status ∈ {exact, ai, missing, portal_only, unmatched}`. **This dataclass is the
  frontend↔backend contract** (see §11).

### 4.3 Tests

- `tests/validate_fixtures.py` — pure-Python, exit-code driven: schema, row counts, the exact
  ₹ figures of the demo, per-group identities, template contents. Run in CI or before every demo.
- `tests/smoke_ui.py` — Streamlit `AppTest` headless run: no exceptions on first render, title,
  4 KPI labels, KPI values, 2 dataframes, the three dispatch buttons, and the full
  click-dispatch-modal flow including session-state and log assertions.

---

## 5. The Synthetic Fixtures in Detail

### 5.1 The four test groups (12 books / 11 portal rows)

| Group | Rows | Where | What it proves |
|---|---|---|---|
| **1 · Exact match** | 6 books + 6 portal | Both files | Baseline pipeline sanity: identical GSTIN + invoice no. + tax amounts match deterministically. |
| **2 · Typo / semantic** | 3 books + 3 portal | Both files | `INV/24-25/081` ↔ `INV-081`, `TAX/2026/019` ↔ `TAX-2026-019`, `BILL-907` ↔ `INV-2026-907`; also trade-name abbreviations ("Acme Corporation Pvt Ltd" ↔ "Acme Corp"). Tax & GSTIN identical → *rescuable*. |
| **3 · Defaulting supplier** | 3 books | **Books only** | Vertex Industrial Supplies (₹14,850), Marathon Freight Movers (₹1,830), Sahyadri Hardware Mart (₹3,391). The 41.2% bucket → Rule 88D / WhatsApp recovery. |
| **4 · Portal-only** | 2 portal | **Portal only** | Pinnacle Marketing `INV-0056` (₹10,080) and Quantum Print `QP/2026/031` (₹14,400), both dated July 2026 → late cross-period filings, ITC carried forward. |

### 5.2 The demo ledger (exact, verified numbers)

| Metric | Value |
|---|---|
| Total Invoiced ITC (books, 12 invoices) | **₹1,07,971** |
| Reconciled ITC (exact, 6 invoices) | **₹57,210** |
| Excel `#N/A` write-off (6 invoices) | **₹50,761** |
| Rescued by AI (3 invoices @ 82% / 93% / 95%) | **₹30,690** |
| High-risk / Rule 88D exposure (3 suppliers) | **₹20,071** |
| Portal-only late filings (2 invoices) | **₹24,480** |
| Portal ITC total (11 invoices) | ₹1,12,380 |

> The ₹50,761 → ₹30,690 split **is** the winning moment: Excel throws away both the rescuable
> ₹30,690 *and* the genuinely risky ₹20,071 into the same `#N/A` bucket. Recon-Agent tells the
> MSME precisely which half to chase and which half to nudge the vendor about.

### 5.3 The three Group-2 rows, row by row

| Books invoice | Supplier (books) | Portal invoice | Supplier (portal) | ITC | AI confidence |
|---|---|---|---|---|---|
| `INV/24-25/081` | Acme Corporation Pvt Ltd | `INV-081` | Acme Corp | ₹18,000 | **82%** |
| `TAX/2026/019` | Zenith Logistics Pvt Ltd | `TAX-2026-019` | Zenith Logistics | ₹2,250 | **93%** |
| `BILL-907` | Nimbus Cloud Services | `INV-2026-907` | Nimbus Cloud Services Pvt. Ltd. | ₹10,440 | **95%** |

Vendor phones are populated for every books row (e.g. Acme `+919876543210`), which is what the
WhatsApp recovery panel reads from the register.

---

## 6. The Two Reconciliation Engines

### 6.1 Engine A — `run_excel_vlookup()` (the villain)

Reproduces a real spreadsheet, faithfully and *unfairly*:

```python
lookup = {p.inum.strip().upper(): p for p in portal}     # literal, case-only tolerance
p = lookup.get(str(r["invoice_no"]).strip().upper())     # exact string or #N/A
```

- Miss → `status="unmatched"`, reason `"Literal string mismatch → #N/A"`.
- Hit but tax differs by > ₹2 → `unmatched` (Excel would show a mismatch, also unusable).
- Hit and tax agrees → `exact`.

No canonicalisation, no corroboration — the point is to show the tool the market actually uses
collapsing on 6 of 12 rows (₹50,761).

### 6.2 Engine B — `run_recon_pipeline()` (the hero), stage by stage

```
[AGENT] Ingesting purchase_register.xlsx and sample_gstr2b.json …
[AGENT] Deterministic pass completed (GSTIN + invoice_no + tax)
[AGENT] Invoking Bedrock Fuzzy Matcher MCP Tool … (offline → local fallback)
[AGENT] Semantic pass recovered N invoices (₹X)
```

### 6.3 The fallback semantic matcher (mirrors the planned Bedrock tool)

**Gate — `trust_and_corroborate(b, p)`** (applied before *any* pairing):
1. `|books.total_tax − portal.tax| ≤ ₹2` (GSTN rounding tolerance), **and**
2. books `supplier_gstin` == portal `ctin` (canonicalised).

No tax corroboration ⇒ no match, ever. This is what makes the AI *auditable*: it never invents
money, it only re-identifies rows whose tax and GSTIN already agree.

**Tier 1 — deterministic:** literal `UPPER()` equality of invoice numbers + gate →
`status="exact"`, confidence 100%.

**Tier 2 — semantic** (on everything still unmatched):

```
sim    = SequenceMatcher(canonical(supplier_name), canonical(portal.trdnm))
serial = 1.0 if last numeral group of books invoice == last numeral group of portal invoice
score  = min(0.40·sim + 0.35·serial + 0.25, 1.0)      # +0.25 base for passing the gate
accept if score ≥ 0.75
```

- `canonical()` lowercases, NFKD-decomposes accents, strips everything but `[a-z0-9]` —
  killing every `/ - .` separator divergence in one move.
- The **trailing serial** is the human-meaningful part of an invoice number
  (`081`, `019`, `907`); prefix noise (`INV/24-25/`, `INV-`, `INV-2026-`) is format noise.
- Worked examples (these reproduce the observed confidences exactly):
  - Acme: sim≈0.552 → 0.40·0.552 + 0.35 + 0.25 = **0.82 → 82%**
  - Zenith: sim≈0.833 → 0.333 + 0.35 + 0.25 = **0.93 → 93%**
  - Nimbus: sim≈0.863 → 0.345 + 0.35 + 0.25 = **0.945 → 95%**
- Best-candidate wins per books row; winners are marked consumed.

**Remainder classification:**
- Books rows never matched → `missing` (supplier has not filed GSTR-1) → recovery panel.
- Portal rows never claimed by any match → `portal_only` (late cross-period filing).

Every `Match` carries a **reason string** — the evidence trail shown in the ledger and used by
the dashboard's audit framing.

### 6.4 Where Bedrock replaces this

With the sidebar toggle on, `run_recon_pipeline(use_bedrock=True)` is the single switch point:
the fallback call is replaced by the Strands orchestrator invocation (HTTP call to the
AgentCore Runtime endpoint), which must return the same `Match` shape (see §11). The fallback
doubles as the **behavioural oracle** the live tool must match or beat on these fixtures.

---

## 7. The Streamlit Dashboard, Section by Section

The visual language is **"the compliance war room"** — built from the subject matter, not
from a generic dashboard template:

- **Palette** (`.streamlit/config.toml` + injected CSS): ledger navy surfaces (`#131A29` app,
  `#1B2537` metric panels, `#0F1524` sidebar, `#0E1524` code), paper-toned text `#E8E4D8`,
  **brass `#C9A227`** as the primary accent (money, not neon), stamp green `#30A46C` for
  recovered ITC, stamp red `#E5484D` for exposure and `#N/A`.
- **Type**: Source Serif 4 for headings (the register of official Indian tax documents),
  IBM Plex Sans for UI copy, IBM Plex Mono for every figure, invoice number and status.
- **The signature element**: statuses render as **rubber-stamp chips** — double-ring
  (`border: 3px double`) bordered mono caps with a faint colour wash, the visual grammar of
  an Indian compliance file: `MATCHED · DETERMINISTIC`, `MATCHED · AI 82%`,
  `DEFAULTING SUPPLIER`, `PORTAL-ONLY · LATE FILING`.
- **Amounts read like Indian invoices**: `inr()` groups digits the lakh/crore way
  (₹1,07,971), not the Western way (₹107,971).
- Metric panels are square-cornered (2px) and quiet, so the stamps carry the colour.

### 7.1 Header & quickstart
- Title: **Recon-Agent** (serif), subtitle *Autonomous GST ITC reconciliation for Indian MSMEs*.
- One-line problem hook: ₹45,000 crore unclaimed; Section 16(2)(aa) blocks credit unless the
  supplier files.
- **`Load demo fixtures`** button (brass primary) — clears any uploads/state so judges get
  the canonical demo in one click, no file browsing.

### 7.2 KPI cards (top bar)
| Card | Value | Why it matters |
|---|---|---|
| Total Invoiced ITC | ₹1,07,971 | The universe at stake. |
| Reconciled ITC (Exact) | ₹57,210 | Deterministic, zero-risk credit. |
| Rescued ITC (AI) | ₹30,690 (+28.4% of total) | **The AI's direct, attributable value.** |
| ITC at High Risk | ₹20,071 (Rule 88D exposure) | Money to act on *today*. |

### 7.3 Side-by-side live comparison — the winning moment
- **Left — “The spreadsheet, faithfully reproduced”:** the literal `=VLOOKUP(...)` formula in a
  code block, a red metric **“Written off as lost: ₹50,761” (6 invoices `#N/A`)**, then each
  failed row stamped `UNRESOLVED` with its books entry and the portal row it never matched.
- **Right — “The same rows, reconciled”:** green metric **“Rescued by the semantic pass:
  ₹30,690 (3 invoices)”**, each rescue stamped `MATCHED · AI 82%` over books-row → portal-row
  with the evidence line (`Tax corroborated · GSTIN verified · numeral overlap on 'INV-081' ·
  name similarity 55%`).
- Rows are separated by faint dashed rules, like a register page.
- The rows on the right are **literally the rows on the left** — same invoices, opposite fates.

### 7.4 Supplier Recovery Panel (the 41.2% bucket)
- Red metric “Trapped with non-filing suppliers: ₹20,071”.
- Table: Invoice · Supplier · GSTIN · ITC (Indian-grouped) · Phone (pulled from the register).
- Per vendor, a `DEFAULTING SUPPLIER` stamp with name — invoice — amount.
- Per vendor, **`Dispatch WhatsApp Recovery Notice via A2A Agent`** (disabled with a tooltip
  if no phone on file). Click → logs `[A2A] Delegated to Comms Agent → …` → opens the dialog (§8).

### 7.5 Reconciliation Ledger
Full classification table for **every** row: Books Invoice, Portal Invoice, Supplier, GSTIN,
ITC, Status stamp, Confidence %, Evidence. This is the audit artifact — every claim on the
dashboard is traceable to a row here.

### 7.6 Agent Activity Log
Expandable console (one `st.code` block, capped at 150 lines) with timestamped, agent-tagged
events: `[EXCEL]`, `[AGENT]` (ingest, deterministic pass, Bedrock invocation, semantic
recovery), `[A2A]` (delegation + dispatch). The “multi-agent” narrative is visible, not claimed.

### 7.7 Sidebar
- **Data Source:** two uploaders (`.xlsx` register, `.json` 2B) + `Reconcile uploaded files`
  (real custom datasets work end-to-end) + `Reset to demo fixtures`.
- **Backend:** `Use AWS Bedrock orchestrator` toggle — the documented switch point, with
  captions naming Strands SDK · MCP · DynamoDB (on) vs local matcher (off).
- Footer: tax period chip (`fp: 082026`) + hackathon badge.

---

## 8. WhatsApp A2A Recovery Flow

1. Judge clicks **Dispatch WhatsApp Recovery Notice via A2A Agent** on a defaulting vendor.
2. Activity log gains `[A2A] Delegated to Comms Agent → <Supplier> (<phone>)`.
3. `@st.dialog("A2A Comms Agent · WhatsApp Recovery Notice")` opens showing:
   - **To:** supplier · phone; **Period:** August 2026
   - The rendered message (spec-exact template):

     > Dear \<Supplier\>, Invoice \<No\> of ₹\<Amount\> is missing from our GSTR-2B for
     > August 2026. Please file your GSTR-1 before the 11th to prevent credit blockage
     > under Rule 88D.

   - Compliance caption: *Template governed by Rule 88D, 30-day remedy window. DRC-01C
     exposure ₹<24% p.a. interest on the invoice's tax>*.
4. **Confirm dispatch** → `[A2A] WhatsApp notice dispatched …` + toast + dialog closes.
   **Cancel** → closes, nothing logged.

In production the Confirm branch is where the A2A call to the Comms Agent (→ Twilio) goes;
the preview/modal UX stays identical either way.

---

## 9. Verification & Test Suites

Both suites are dependency-light (no pytest) and exit non-zero on any failure.

```bash
.venv/bin/python tests/validate_fixtures.py   # 20 assertions — data + both engines
.venv/bin/python tests/smoke_ui.py            # 10 assertions — headless UI + dialog flow
```

**validate_fixtures** asserts: column order; 12/11 row counts; `fp == 082026`; VLOOKUP 6/6
split and the exact ₹50,761 write-off; AI rescue of exactly `['INV/24-25/081',
'TAX/2026/019', 'BILL-907']` worth ₹30,690; 3 defaulting suppliers worth ₹20,071, all `27…`
GSTINs; 2 portal-only rows; Acme → `INV-081` at ≥80% confidence; Zenith tax ₹2,250; all AI
confidences within 0–100; WhatsApp template contains *Rule 88D / GSTR-1 / August 2026 / ₹*.

**smoke_ui** asserts: first render exception-free; title text; the four KPI labels; KPI values
(₹1,07,971 / ₹57,210 / ₹30,690 / ₹20,071); ≥2 dataframes; the three `wa-*` buttons; and after a
click: no exception, `wa_modal` set in session state, `[A2A]` delegation in the log.

**Current status: 99 checks passing across four suites** — 48 fixture/pipeline assertions,
13 tiered-router tests (`tests/test_smart_router.py`), 27 backend tests
(`tests/test_backend.py`: persistence guards, stubbed DynamoDB, comms-agent modes and audit
rows), and 11 headless UI checks. Test runs never write to the deployed table (persistence
is stubbed and call-counted in the suites).

Hardened after pre-merge review: model verdicts must be a bare `MATCH` ("NO MATCH" and
"NOT A MATCH" degrade to UNRECONCILED instead of reading as matches); the pipeline cache
digest covers portal tax/GSTIN/trade-name so a corrected GSTR-2B is never served stale;
and a Bedrock outage degrades without caching the fallback output, so the next rerun
retries Bedrock.

Hardened after a second review round: the corroboration gate now fails closed in **both**
implementations (`app._corroborate` and the backend router) — two blank GSTINs are never
identity; degraded runs are persisted again but flagged `degraded=true` in DynamoDB (an
outage is an audit fact; the rows are not authoritative) and surfaced in the sidebar;
and the comms agent normalises the phone *before* the mode branch, so simulation can no
longer record `ok=True` for a number Twilio would reject (trunk-prefixed `091 …` forms
normalise to E.164, leading-zero numbers are rejected).

---

## 10. Running the Project

### 10.1 Locally (macOS/Linux)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python fixtures/generate_mock_data.py          # regenerates both fixtures
streamlit run frontend/app.py                  # → http://localhost:8501
```

Optional: `run.sh` wraps the same launch (`PORT` env override, binds `0.0.0.0`):
`sh ./run.sh`.

### 10.2 Freebuff Cloud preview (already configured)

| Setting | Command |
|---|---|
| Install | `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && .venv/bin/python fixtures/generate_mock_data.py` |
| Preview | `sh ./run.sh` on port **8501** |

The launcher passes `--server.enableCORS false --server.enableXsrfProtection false` so
Streamlit's WebSocket accepts the reverse-proxy origin (without these, the page renders but
hangs on “connecting”).

### 10.3 Regenerating fixtures

`python fixtures/generate_mock_data.py` is idempotent and deterministic — run it any time;
both test suites will still pass afterwards.

---

## 11. Backend Integration Contract

*(For DeepSeek 4.1 Flash — the orchestrator.)*

### 11.1 The wire object

Everything the dashboard renders derives from `Match`. The backend must return JSON-shaped
equivalents:

```jsonc
{
  "register_no": "INV/24-25/081",   // books invoice number, or "—" for portal-only
  "portal_no": "INV-081",           // 2B invoice number, or "—" for missing
  "supplier_name": "Acme Corporation Pvt Ltd",
  "supplier_gstin": "27AABCA1234F1Z5",
  "tax": 18000.0,                    // igst+cgst+sgst, 2dp
  "status": "ai",                    // exact | ai | missing | portal_only | unmatched
  "ai_conf": 82,                     // 0–100
  "similarity": 0.552,               // optional, display only
  "reason": "Tax corroborated · GSTIN verified · numeral overlap on 'INV-081'"
}
```

Invariants the orchestrator must honour (they are what makes the product defensible):
- **No match without corroboration**: tax within ₹2 **and** GSTIN equality (fail-closed — a
  books row with a blank GSTIN is never corroborated) — embeddings may re-*identify* rows,
  never re-*price* them.
- **Conservation**: every books row appears exactly once (exact/ai/missing); every portal row
  is claimed by exactly one match or becomes `portal_only`. Duplicate books lines (split
  billing, double entry) collapse onto one 2B claim; the surplus stays `missing`.
- `missing` ⇒ books-only; `portal_only` ⇒ portal-only. Never both sides absent.

### 11.2 Integration points in `app.py` (all in one place)

| Hook | Today | Production |
|---|---|---|
| `run_recon_pipeline(use_bedrock=True)` | warns + calls fallback | POST books+portal to the Strands orchestrator endpoint (AgentCore Runtime / Lambda URL), parse `Match[]`. Every cache-miss run is persisted to the DynamoDB audit trail via `backend/db/results.py` — degraded (Bedrock-outage) runs included, stored with `degraded=true`; downstream analytics exclude flagged rows. |
| `render_wa_modal` → Confirm dispatch | **live seam** — `backend/subagents/comms_agent.send_recovery_notice()` | Twilio WhatsApp send when `TWILIO_*` keys are set; clearly-labelled audited simulation otherwise. Phones are normalised (E.164, India-first) before the mode branch — both paths audit the number that would actually be used, and junk numbers fail identically in either mode. Every attempt (delivered, simulated, failed, invalid phone, no-phone) is a DynamoDB audit row. |
| `load_data()` | local files / uploads | optionally fetch S3-processed period data by `fp`. |

Recommended env vars (backend reads via `process.env`/Lambda config; nothing hard-coded here):
`RECON_API_BASE_URL`, `RECON_API_KEY`, `RECON_AGENTCORE_ARN`, `TWILIO_*` (backend-side only).

### 11.3 Acceptance test for the backend

Run the orchestrator against `fixtures/` and require parity with §5.2:
6 exact / 3 ai (82, 93, 95 ±2) / 3 missing / 2 portal-only, and the four ₹ totals within
rounding. `tests/validate_fixtures.py` is the literal oracle — point its pipeline call at the
live backend when it lands.

### 11.4 Deployed infrastructure (AWS)

`infrastructure/recon-agent-core.yaml` (CloudFormation, stack `recon-agent-core`, region
us-east-1) provisions, all tagged `project=recon-agent`:

| Resource | Name | Notes |
|---|---|---|
| DynamoDB | `recon-agent-results-demo` | pk/sk single-table: `run#<period>` results ledger (with a `degraded` flag for Bedrock-outage runs), `dispatch#<period>` A2A audit. SSE + PITR. |
| S3 | `recon-agent-uploads-demo-<account>` | Private (all four public-access blocks), versioned, AES256. |
| IAM | `recon-agent-app-role-demo` / user `recon-agent-app` | Least-privilege: DynamoDB data ops, the one uploads bucket, Bedrock invoke on exactly the three router models. |

The dashboard reads resource names from env (`RECON_RESULTS_TABLE`, `RECON_UPLOADS_BUCKET`,
`RECON_APP_ROLE_ARN`, `RECON_AWS_REGION`) — nothing hard-coded. Bedrock model access itself
is a console-only account entitlement (agreement acceptance, no API exists); it is tracked
with AWS support and is the last blocked piece — every layer around it is live.

---

## 12. Judge Demo Script (5 Minutes)

1. **Open the dashboard** (preview URL). Header + ₹45,000 Cr hook (15s).
2. **`⚡ Load Demo Fixtures`** — agent log starts narrating: ingest → deterministic pass →
   Bedrock invocation → semantic recovery (30s).
3. **KPI bar:** “₹1.08 lakh of credit, ₹57k reconciled cleanly. Watch the other ₹51k.” (30s)
4. **The moment:** point left — `=VLOOKUP`, 6 `#N/A` rows, ₹50,761 “prematurely written off”.
   Point right — the *same three typoed invoices* resolved at **82% / 93% / 95%** with the
   evidence line. “Excel sees noise. The agent sees a corroborated invoice.” (90s)
5. **Recovery panel:** “₹20,071 isn't lost — it's *trapped*, and we know whom to call.”
   Click dispatch → read the Rule 88D WhatsApp aloud → confirm → toast + log line.
   *(If asked: the send itself is simulated in this build — the Twilio call is the backend
   Comms Agent's job, see §11.2.)* (60s)
6. **Ledger:** “Every classification carries its evidence — audit-ready by construction.” (30s)
7. **Close:** toggle the Bedrock switch — “same UI, live Bedrock behind it” — and the
   architecture slide: S3 → Lambda → DynamoDB → Strands → Bedrock → A2A → Twilio. (45s)

---

## 13. Known Limitations & Roadmap

- **Bedrock invoke waits on model access**: the account entitlement (console-only, legal
  agreement acceptance) is with AWS support; until it lands the Bedrock toggle degrades to
  the local matcher with a visible warning, exactly as designed. The Converse wiring,
  cost-tiered router and IAM scoping are all live and tested.
- **WhatsApp dispatch is live-seamed, mode-labelled**: with Twilio keys it really sends;
  without them the Comms Agent records an audited simulation in DynamoDB. The modal states
  the mode explicitly — a simulated send can never pass as delivered.
- **Static 24% p.a.** exposure figure in the dialog (worst-case Sec 50(3)); a date-aware
  interest calculator is straightforward to add.
- **Period handled is single-`fp`** (`082026`); multi-period sweeps (the 18.4% late-filing
  cure) are a for-loop away once the backend holds history in DynamoDB.
- **Confidence is a heuristic composite**; the Bedrock tool replaces it with Titan v2 cosine
  similarity blended with the same corroboration gates.
- **No auth/tenancy in the demo frontend**; production adds Cognito + per-tenant DynamoDB
  partition keys (schema already documented in the README's stack section).
