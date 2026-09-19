/**
 * Every language of the Eighth Schedule, plus English.
 *
 * `coverage` is honest, not decorative:
 *   "full" — every string on the page, including the long explanations.
 *   "core" — the interface a user navigates with (sections, buttons, statuses,
 *            table columns, assistant chrome). Explanatory paragraphs remain
 *            in English until a native speaker reviews them, and the page says
 *            so out loud instead of pretending otherwise.
 */
export interface LocaleMeta {
  code: string;
  english: string;
  native: string;
  dir: "ltr" | "rtl";
  coverage: "full" | "core";
}

export const LOCALES: LocaleMeta[] = [
  { code: "en", english: "English", native: "English", dir: "ltr", coverage: "full" },
  { code: "hi", english: "Hindi", native: "हिन्दी", dir: "ltr", coverage: "full" },
  { code: "bn", english: "Bengali", native: "বাংলা", dir: "ltr", coverage: "core" },
  { code: "mr", english: "Marathi", native: "मराठी", dir: "ltr", coverage: "core" },
  { code: "ta", english: "Tamil", native: "தமிழ்", dir: "ltr", coverage: "core" },
  { code: "te", english: "Telugu", native: "తెలుగు", dir: "ltr", coverage: "core" },
  { code: "gu", english: "Gujarati", native: "ગુજરાતી", dir: "ltr", coverage: "core" },
  { code: "kn", english: "Kannada", native: "ಕನ್ನಡ", dir: "ltr", coverage: "core" },
  { code: "ml", english: "Malayalam", native: "മലയാളം", dir: "ltr", coverage: "core" },
  { code: "pa", english: "Punjabi", native: "ਪੰਜਾਬੀ", dir: "ltr", coverage: "core" },
  { code: "or", english: "Odia", native: "ଓଡ଼ିଆ", dir: "ltr", coverage: "core" },
  { code: "as", english: "Assamese", native: "অসমীয়া", dir: "ltr", coverage: "core" },
  { code: "ur", english: "Urdu", native: "اردو", dir: "rtl", coverage: "core" },
  { code: "ne", english: "Nepali", native: "नेपाली", dir: "ltr", coverage: "core" },
  { code: "sa", english: "Sanskrit", native: "संस्कृतम्", dir: "ltr", coverage: "core" },
  { code: "kok", english: "Konkani", native: "कोंकणी", dir: "ltr", coverage: "core" },
  { code: "mai", english: "Maithili", native: "मैथिली", dir: "ltr", coverage: "core" },
  { code: "doi", english: "Dogri", native: "डोगरी", dir: "ltr", coverage: "core" },
  { code: "ks", english: "Kashmiri", native: "کٲشُر", dir: "rtl", coverage: "core" },
  { code: "mni", english: "Manipuri", native: "মৈতৈলোন্", dir: "ltr", coverage: "core" },
  { code: "brx", english: "Bodo", native: "बड़ो", dir: "ltr", coverage: "core" },
  { code: "sat", english: "Santali", native: "ᱥᱟᱱᱛᱟᱲᱤ", dir: "ltr", coverage: "core" },
  { code: "sd", english: "Sindhi", native: "سنڌي", dir: "rtl", coverage: "core" },
];

/**
 * The interface every locale translates. Keep this list to what a user needs
 * to find their way around the page — sections, the four figures, the status
 * labels, the table columns, and the actions.
 */
export const CORE_KEYS = [
  "nav_numbers",
  "nav_compare",
  "nav_recovery",
  "nav_ledger",
  "nav_log",
  "nav_glossary",
  "nav_start",
  "nav_submit",
  "nav_language",
  "theme_light",
  "theme_dark",
  "hero_title",
  "cta_start",
  "cta_numbers",
  "kpi_total",
  "kpi_exact",
  "kpi_rescued",
  "kpi_risk",
  "status_matched",
  "status_recovered",
  "status_defaulting",
  "status_late",
  "unresolved",
  "ledger_title",
  "col_books",
  "col_portal",
  "col_supplier",
  "col_gstin",
  "col_itc",
  "col_status",
  "col_conf",
  "col_evidence",
  "search",
  "filter",
  "show",
  "rows",
  "of",
  "recovery_title",
  "dispatch",
  "log_title",
  "glossary_title",
  "gs_title",
  "submit_title",
  "submit_sub",
  "submit_choose",
  "submit_change",
  "submit_run",
  "asst_launch",
  "login_skip",
  "confirm",
  "cancel",
  "sent",
  "not_sent",
  "empty_filter",
  "page_prev",
  "page_next",
  "nav_home",
  "group_reconcile",
  "palette_placeholder",
  "palette_empty",
  "source_demo",
  "source_own",
  "login_signup_title",
  "login_signup_sub",
  "login_name",
  "login_register",
  "login_password_hint",
  "login_have_account",
  "login_no_account",
  "login_or",
  "login_continue_with",
  "login_provider_error",
] as const;

export const DEFAULT_LANG = "en";

export function localeOf(code: string): LocaleMeta {
  return LOCALES.find((l) => l.code === code) ?? LOCALES[0];
}
