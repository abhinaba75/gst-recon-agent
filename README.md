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

## 📚 Documentation

**Everything is documented in [`DOCUMENTATION.md`](DOCUMENTATION.md)** — the domain problem,
fixtures (all four test groups with exact figures), both reconciliation engines (the Excel
VLOOKUP villain vs the semantic AI pipeline), the dashboard section by section, the WhatsApp
A2A recovery flow, the 30-check test suites, and the backend integration contract for the
AWS Bedrock / Strands orchestrator.

## ✅ Verify

```bash
python tests/validate_fixtures.py   # 20 data + pipeline assertions
python tests/smoke_ui.py            # 10 headless UI assertions
```
