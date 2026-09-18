"""Recon-Agent backend — the agent layer the frontend delegates to.

Layout (each subpackage has one job):
- tools/      : Bedrock-backed tools the orchestrator calls (smart_router, …)
- parser/     : document parsers (Excel register, GSTN GSTR-2B JSON, …)
- subagents/  : A2A agents (Comms Agent → Twilio WhatsApp, …)
- db/         : persistence (DynamoDB audit trail, period history, …)

The orchestrator module is the single seam the Streamlit frontend calls
into; when the Strands/Lambda orchestrator lands it implements the same
Match contract documented in DOCUMENTATION.md §11.
"""
