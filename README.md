# Recon-Agent ⚡

> Autonomous, Multi-Agent GST Input Tax Credit (ITC) Reconciliation & Supplier Recovery Engine.

[![Built on AWS](https://img.shields.io/badge/Built%20on-AWS%20Bedrock-FF9900?logo=amazon-aws)](https://aws.amazon.com/bedrock/)
[![Framework](https://img.shields.io/badge/Agentic%20Framework-Strands%20SDK-0A84FF)](https://github.com/)
[![Compliance](<https://img.shields.io/badge/GST%20Compliance-Rule%2088D%20%7C%20Sec%2016(2)(aa)-10B981>)](#)
[![Hackathon](https://img.shields.io/badge/WeMakeDevs-AWS%20First%20Commit%202026-8B5CF6)](#)

---

## 📌 Problem Overview: The ₹45,000 Crore ITC Leakage

In the modern Indian GST compliance ecosystem, claiming Input Tax Credit (ITC) has evolved from self-assessment to strictly automated reconciliation:

- **Section 16(2)(aa):** Buyers can strictly claim credit **only** if the supplier has declared the invoice in their GSTR-1 return.
- **Rule 88D (Form DRC-01C):** Automatic system-generated tax notices are dispatched if GSTR-3B Table 4 claims exceed auto-drafted GSTR-2B figures by more than the tolerance threshold.
- **Section 50(3) Exposure:** Wrongful utilization triggers interest at **18% to 24% p.a.**, mandatory DRC-03 recovery, and potential GSTIN suspension under Rule 59(6).

Analysis of over 2.4 million invoice lines across 500+ corporate entities highlights that **over ₹45,000 Crore** in legitimate ITC goes unclaimed annually due to systemic operational friction:

| Friction Point          | Root Cause                                                                             | Frequency |
| :---------------------- | :------------------------------------------------------------------------------------- | :-------- |
| **Supplier Non-Filing** | Vendors collect GST but miss the 11th/13th GSTR-1 cutoff                               | **41.2%** |
| **Data Entry Typos**    | Internal registers differ slightly from portal records (`INV/24-25/081` vs. `INV-081`) | **28.6%** |
| **Delayed Filings**     | Cross-period invoices filed 1–3 months late requiring manual multi-period sweeps       | **18.4%** |
| **Rate Restructuring**  | HSN/SAC confusion under GST 2.0 slabs (5%/18%/40%) and CGST/SGST/IGST mismatches       | **11.8%** |

Traditional accounting teams burn hundreds of manual hours in Microsoft Excel using brittle `=VLOOKUP` equations that break on simple typos. **Recon-Agent replaces manual spreadsheet manipulation with an autonomous, agentic pipeline.**

---

## 💡 The Solution: Recon-Agent

Recon-Agent is a cloud-native, multi-agent AI system built on the **Strands Agents SDK** and powered by **Amazon Bedrock**. It reconciles raw internal purchase registers against auto-drafted GSTR-2B datasets, resolves typographic and semantic mismatches, and autonomously dispatches context-aware WhatsApp reminders to defaulting vendors.

### Core Capabilities

- **Semantic & Deterministic Hybrid Matching:** Combines fast string metric pre-filtering with Amazon Titan Text v2 embeddings and Claude 3.5 Sonnet to match distorted invoice strings without human intervention.
- **Autonomous Vendor Communication:** Uses agent-to-agent (A2A) delegation to draft and dispatch compliant, polite WhatsApp follow-ups via Twilio API.
- **Compliance Guardrails:** Uses Amazon Bedrock Guardrails to prevent mathematical hallucinations and enforce professional tone in vendor communications.
- **Stateless Fault Tolerance:** Integrates `strands-dynamodb-storage` to preserve session state across multi-period audits.

---

## 🏗️ System Architecture

                              +-------------------------------------------------+
                              |                 AWS CLOUD                       |
                              |                                                 |

+------------------+ | +---------------+ +------------------+ |
| Internal Ledger | | | Amazon S3 | --> | AWS Lambda | |
| (Excel / CSV) | --Upload-> | | Data Bucket | | Ingestion Parser | |
+------------------+ | +---------------+ +--------+---------+ |
| GSTR-2B Data | | | |
| (JSON / Excel) | | v |
+------------------+ | +------------------+ |
| | Amazon DynamoDB | |
| | Ledger State / | |
| | Session Memory | |
| +--------+---------+ |
| | |
| v |
| +-----------------------------------------+ |
| | Bedrock AgentCore Runtime | |
| | (Claude 3.5 Sonnet via Strands SDK) | |
| +----+-------------------------------+----+ |
| | | |
| | (Fuzzy Tool) | (A2A) |
| v v |
| +---------------+ +----------------+ |
| | AgentCore | | Communication | |
| | Gateway | | Agent (Strands | |
| | (Titan Text) | | A2AServer) | |
| +---------------+ +--------+-------+ |
| | |
+---------------------------------------|---------+
v
+-------------------------+
| Twilio WhatsApp API |
| Defaulting Vendor Alert |
+-------------------------+

---

## 🛠️ AWS Stack & Technologies

- **Orchestration & Reasoning:** Amazon Bedrock (Anthropic Claude 3.5 Sonnet)
- **Embeddings & Fuzzy Logic:** Amazon Titan Text v2 via Bedrock AgentCore Gateway
- **Agent Framework:** Strands Agents SDK (`strands-agents`, `strands-dynamodb-storage`)
- **State Management:** Amazon DynamoDB (Partition: `TenantId`, Sort: `InvoiceNumber`)
- **File Storage:** Amazon S3
- **Compute:** AWS Lambda (Python 3.12 runtime)
- **Safety & Guardrails:** Amazon Bedrock Guardrails
- **Outbound Messaging:** Twilio Messaging API (WhatsApp Sandbox)
- **Frontend:** Streamlit / React

---

## 📂 Project Structure

```text
recon-agent/
├── backend/
│   ├── orchestrator.py           # Primary Strands Agent orchestrator
│   ├── subagents/
│   │   └── comms_agent.py        # A2A vendor recovery communication agent
│   ├── tools/
│   │   ├── fuzzy_matcher.py      # MCP Tool: Hybrid string & Titan v2 embeddings
│   │   └── twilio_client.py      # WhatsApp dispatch integration
│   ├── db/
│   │   └── dynamodb_handler.py   # State persistence & invoice schema
│   └── parser/
│       └── gstr2b_ingest.py      # S3-triggered Lambda ingestion parser
├── frontend/
│   └── app.py                    # Streamlit/React compliance dashboard
├── fixtures/
│   ├── sample_purchase_register.xlsx
│   └── sample_gstr2b.json
├── requirements.txt
└── README.md
```
