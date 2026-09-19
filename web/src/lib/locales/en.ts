/**
 * Canonical copy, in English. Every other locale overrides a subset of these
 * keys; anything not overridden falls back here rather than rendering a key
 * name or an empty string.
 *
 * Written for the person who owns the money: short sentences, no jargon left
 * unexplained, and the legal reference always attached to the claim.
 */
export const EN: Record<string, string> = {
  brand_tagline: "GST credit recovery for Indian MSMEs",

  nav_numbers: "Numbers",
  nav_compare: "Excel vs agent",
  nav_recovery: "Recovery",
  nav_ledger: "Ledger",
  nav_log: "Activity",
  nav_glossary: "Labels",
  nav_start: "Get started",
  nav_submit: "Submit bills",
  nav_sections: "Sections",
  nav_language: "Language",
  nav_menu: "Menu",
  skip_to_main: "Skip to main content",

  theme_light: "Light",
  theme_dark: "Dark",
  theme_to_light: "Switch to day mode",
  theme_to_dark: "Switch to night mode",
  theme_now_light: "Day mode on",
  theme_now_dark: "Night mode on",

  hero_eyebrow: "AWS First Commit · WeMakeDevs",
  hero_title: "The tax credit your spreadsheet wrote off",
  hero_sub:
    "Recon-Agent matches every purchase bill against GSTR-2B, recovers what a VLOOKUP cannot see, and messages the vendors who have not filed.",
  hero_body:
    "Section 16(2)(aa) allows credit only when the supplier files, and Rule 88D starts an automatic notice when your claim disagrees with the portal. This page shows what is safe, what was recovered, and what needs a phone call today.",
  cta_numbers: "See the numbers",
  cta_compare: "Excel vs agent",
  cta_start: "Get started",
  cta_start_hint: "Four steps, about ten minutes",

  chart_title: "Credit per bill, coloured by outcome",
  chart_sub:
    "Every bill in this period, largest first. The same figures appear in the ledger below.",
  kpi_title: "Four figures for this period",
  kpi_bills: "purchase bills",
  kpi_portal_rows: "GSTR-2B rows",
  kpi_total: "Total Invoiced ITC",
  kpi_exact: "Reconciled ITC (Exact)",
  kpi_rescued: "Rescued ITC (AI)",
  kpi_risk: "ITC at High Risk",
  kpi_note:
    "In plain words: the first figure is all the GST credit sitting in your bills; the second already matches the government's record; the third is credit the agent recovered that Excel lost; the fourth is money trapped with vendors who have not filed.",
  kpi_of_total: "of total credit",
  kpi_rule88d: "Rule 88D exposure",
  kpi_zero_risk: "zero-risk, already matching",

  compare_title: "The same twelve rows, two outcomes",
  compare_left: "The spreadsheet, faithfully reproduced",
  compare_right: "The same rows, reconciled",
  compare_left_body:
    "A literal cell comparison cannot see past a separator. Every miss lands in one pile — the recoverable and the genuinely risky alike.",
  compare_right_body:
    "Tax corroborated to the rupee and GSTIN verified before any match is proposed. The agent re-identifies rows; it never invents money.",
  written_off: "Written off as lost",
  written_off_delta: "invoices return #N/A",
  rescued_metric: "Recovered by the agent",
  rescued_delta: "invoices the spreadsheet had written off",
  unresolved: "UNRESOLVED",
  portal_row: "Portal row never matched",
  formula_label: "The formula it uses",
  rules_label: "What the agent checks before matching",
  rule_gstin: "The supplier's GSTIN must match exactly.",
  rule_tax: "The tax on the bill must agree to the rupee.",
  rule_number: "The invoice number may differ only in separators or formatting.",

  submit_title: "Submit bills and documents",
  submit_sub: "Your purchase register and the GSTR-2B file for the same month.",
  submit_body:
    "Both documents go straight to the reconciliation engine and are read in memory — nothing is stored on this page or on disk. Submit with neither file chosen to see the bundled sample period.",
  submit_register_label: "Purchase register",
  submit_register_hint: "Excel (.xlsx) or CSV · one row per bill",
  submit_portal_label: "GSTR-2B download",
  submit_portal_hint: "JSON from the GST portal for the same period",
  submit_choose: "Choose file",
  submit_change: "Change file",
  submit_selected: "Selected",
  submit_none: "No file chosen",
  submit_clear: "Clear chosen file",
  submit_run: "Reconcile my documents",
  submit_demo_run: "Run the sample documents",
  submit_busy: "Reconciling…",
  submit_ok: "Reconciled",
  submit_failed: "Not reconciled",
  submit_reset: "Back to the sample period",
  submit_source_note:
    "Showing reconciliation results for the documents submitted just now. Press the reset button to return to the bundled sample period.",
  submit_privacy:
    "Your files are read in memory to produce the figures on this page. Nothing is written to disk and nothing is shared.",

  recovery_title: "Supplier recovery",
  recovery_sub: "Trapped with non-filing suppliers",
  recovery_body:
    "These vendors collected the tax but have not filed GSTR-1, so the credit is not allowed yet. Send the notice now — the remedy window is 30 days.",
  dispatch: "Send recovery notice",
  no_contact: "No phone or email in the register",

  dialog_title: "Recovery notice · Rule 88D",
  dialog_to: "To",
  dialog_period: "Period",
  dialog_message: "Message",
  dialog_exposure:
    "Rule 88D remedy window is 30 days. Interest exposure at 24% p.a. on this invoice's tax:",
  dialog_footer:
    "Nothing is sent until you confirm. The notice quotes your books and the GSTR-2B position for this period.",
  login_title: "Sign in to the workspace",
  login_sub: "GST credit recovery for Indian MSMEs",
  login_email: "Email",
  login_password: "Password",
  login_submit: "Sign in",
  login_checking: "Checking…",
  login_demo_hint: "Demo workspace: demo@recon-agent.in · demo-88d",
  login_note:
    "This build has one workspace and no user accounts of its own. A production deployment puts this page behind your own GST-suite login or SSO, and the credentials are verified by the engine, never by the browser.",
  login_skip: "Skip sign-in (demo)",
  login_skip_note:
    "Opens the demo workspace without verification. The figures are the last exported run and recovery notices will not be delivered.",
  login_failed: "Those credentials did not match.",
  login_offline:
    "The reconciliation engine is not reachable, so sign-in cannot be verified. The engine is what holds the session, not this page.",
  login_benefits: "What is behind this sign-in",
  offline_session:
    "No engine is connected. This session was admitted by the browser using the published demo credentials — nothing was verified, the figures are the last exported run, and recovery notices will not be delivered.",
  sign_out: "Sign out",
  signed_in_as: "Signed in as",

  sending: "Sending…",
  confirm: "Confirm and send",
  cancel: "Cancel",
  close: "Close",
  copy_message: "Copy message",
  copied: "Message copied",
  sent: "Sent",
  sent_note: "Delivered to the supplier's registered contact.",
  not_sent: "Not sent",
  channel_whatsapp: "WhatsApp",
  channel_email: "Email",
  channel_none: "No messaging channel",

  ledger_title: "Reconciliation ledger",
  ledger_sub: "Every classification, with the evidence behind it. Search or filter by status.",
  search: "Search supplier, invoice or GSTIN",
  search_example: "e.g. Vertex or INV/24-25/088…",
  filter: "Filter by status",
  all: "All",
  status_matched: "Matched",
  status_recovered: "Recovered by agent",
  status_defaulting: "Defaulting supplier",
  status_late: "Late filing",
  show: "Showing",
  of: "of",
  rows: "rows",
  col_books: "Books invoice",
  col_portal: "Portal invoice",
  col_supplier: "Supplier",
  col_gstin: "GSTIN",
  col_itc: "ITC",
  col_status: "Status",
  col_conf: "Confidence",
  col_evidence: "Evidence",
  sort_itc_desc: "ITC, largest first",
  sort_itc_asc: "ITC, smallest first",
  empty_filter: "No rows match that filter.",
  page_prev: "Previous",
  page_next: "Next",
  nav_home: "Home",
  group_reconcile: "Reconciliation",
  palette_placeholder: "Search sections, suppliers, invoices…",
  palette_empty: "Nothing matches that search.",
  source_demo: "Bundled sample (synthetic)",
  source_own: "Your submitted documents",
  login_signup_title: "Create an account",
  login_signup_sub: "Your workspace, your documents.",
  login_name: "Full name",
  login_register: "Create account",
  login_password_hint: "At least 8 characters.",
  login_have_account: "Already have an account?",
  login_no_account: "New here?",
  login_or: "or",
  login_continue_with: "Continue with",
  login_provider_error: "That sign-in could not be completed. Please try again.",

  log_title: "Reconciliation activity",
  log_sub: "Every step of this period's reconciliation, in the order it happened.",
  tag_data: "Source data",
  tag_excel: "Spreadsheet",
  tag_agent: "Reconciliation",
  tag_notice: "Vendor notice",

  glossary_title: "What the labels mean",
  g_exact: "The bill and the government record agree exactly. The credit is safe to claim.",
  g_ai: "The invoice number or vendor name differed slightly, but tax and GSTIN agreed, so the agent identified the same bill. Credit recovered.",
  g_missing:
    "The bill is in your books but the vendor has not filed GSTR-1, so credit is not allowed yet under Section 16(2)(aa).",
  g_portal_only:
    "The vendor filed late and the credit has now appeared in GSTR-2B. Claim it this period.",

  gs_title: "Get started",
  gs_sub: "Four steps, no new software to learn.",
  gs_prereq_title: "What you need before you start",
  gs_prereq_1: "Your purchase register as an Excel file, one row per bill.",
  gs_prereq_2: "The GSTR-2B JSON downloaded from the GST portal for the same month.",
  gs_prereq_3: "Each vendor's phone number or email, so a notice can reach them.",
  gs_step1_t: "Load the two documents",
  gs_step1_d:
    "Choose your purchase register and GSTR-2B file in Submit bills below, or run the bundled sample to see the demo period. Looking around sends nothing.",
  gs_step2_t: "Run the reconciliation",
  gs_step2_d:
    "Every bill is compared on GSTIN, invoice number and tax. Exact matches settle immediately; near matches are checked against the tax and GSTIN before the agent accepts them.",
  gs_step3_t: "Read the four figures",
  gs_step3_d:
    "Safe credit, recovered credit, credit at risk, and what the spreadsheet had written off. The ledger below every figure shows the evidence behind it.",
  gs_step4_t: "Send the recovery notices",
  gs_step4_d:
    "For vendors who have not filed, send the Rule 88D notice by WhatsApp or email from the recovery list, then confirm. Every attempt is recorded either way.",
  gs_demo: "Load the demo data",
  gs_demo_note:
    "The bundled register is synthetic. No real GSTIN, invoice or vendor is represented.",
  gs_need_console:
    "Your own files are reconciled in the Submit bills section above — the engine reads them in memory and nothing is stored.",
  gs_data_title: "Where the GSTR-2B file comes from",
  gs_data_d:
    "On the GST portal, open Returns Dashboard, choose the month, then Download GSTR-2B (JSON). Save the file unopened — the agent reads the portal's own format.",
  gs_help_title: "If something looks wrong",
  gs_help_d:
    "A bill marked as a defaulting supplier means the vendor has not filed. Ask the assistant, or check the Labels section, before treating a figure as final.",

  asst_launch: "Ask the assistant",
  asst_title: "Recon-Agent assistant",
  asst_sub: "Ask about this page, the figures, or GST credit rules",
  asst_placeholder: "Type your question…",
  asst_send: "Send",
  asst_thinking: "Thinking…",
  asst_clear: "Clear conversation",
  asst_close: "Close assistant",
  asst_suggest: "Suggested questions",
  asst_q1: "What should I do first?",
  asst_q2: "Why is a bill at high risk?",
  asst_q3: "What is Rule 88D?",
  asst_q4: "How much credit did we recover?",
  asst_source_guide: "Answered from the built-in guide",
  asst_source_model: "Answered by the language model",
  asst_offline:
    "No language model is connected right now, so answers come from the built-in guide and the figures on this page.",
  asst_empty: "Nothing yet. Ask a question below, or pick one of the suggestions.",
  asst_error: "That question could not be answered just now. Please try again.",
  asst_no_answer:
    "I do not have that in the built-in guide. Try asking about the four figures, a supplier status, Rule 88D, or how to send a recovery notice.",
  asst_disclaimer:
    "Guidance on this app and the reconciliation it performs. It is not legal or tax advice — confirm filings with your accountant.",

  snapshot_note:
    "Reconciled from the purchase register and GSTR-2B for this period. Every figure is reproducible from those two documents.",
  footer_legal: "Section 16(2)(aa) · Rule 88D / DRC-01C · Section 50(3)",
  footer_fixtures:
    "Demo fixtures are synthetic. No real GSTIN, invoice or vendor is represented.",
  back_to_top: "Back to top",
  coverage_note:
    "The interface of this page is translated. Longer explanations are still being reviewed by native speakers and appear in English meanwhile.",
};
