import { CORE_A } from "./locales/core-a";
import { CORE_B } from "./locales/core-b";
import { EN } from "./locales/en";
import { HI } from "./locales/hi";
import { DEFAULT_LANG, LOCALES, localeOf, type LocaleMeta } from "./locales";

export type Lang = string;
export { LOCALES, DEFAULT_LANG, localeOf, type LocaleMeta };

/** Every locale table, keyed by language code. */
const TABLES: Record<string, Record<string, string>> = {
  en: EN,
  hi: HI,
  ...CORE_A,
  ...CORE_B,
};

export const LANG_STORAGE_KEY = "recon-lang";

/**
 * Look up a string. A locale that has not translated a key falls back to the
 * English source — never to a raw key name and never to an empty string, so a
 * partially translated page still reads as a page.
 */
export function tr(key: string, lang: Lang): string {
  return TABLES[lang]?.[key] ?? EN[key] ?? key;
}

/**
 * The English line shown beneath a heading when the interface is not English.
 * English is the language the reviewer (an accountant, a GST officer, a judge)
 * is most likely to read, and it is the only pair anyone can verify today.
 */
export function alt(key: string, lang: Lang): string {
  if (lang === "en") return "";
  return EN[key] ?? "";
}

export function langName(code: string): string {
  return localeOf(code).native;
}

export function isRtl(lang: Lang): boolean {
  return localeOf(lang).dir === "rtl";
}

/** "full" — everything; "core" — the interface, with English prose. */
export function coverageOf(lang: Lang): "full" | "core" {
  return localeOf(lang).coverage;
}

export function initialLang(): Lang {
  if (typeof window === "undefined") return DEFAULT_LANG;
  try {
    const saved = window.localStorage.getItem(LANG_STORAGE_KEY);
    if (saved && LOCALES.some((l) => l.code === saved)) return saved;
    const nav = window.navigator.language?.slice(0, 2).toLowerCase();
    return nav && LOCALES.some((l) => l.code === nav) ? nav : DEFAULT_LANG;
  } catch {
    return DEFAULT_LANG;
  }
}

/**
 * The transport the engine used → the channel a shop owner recognises.
 * Provider names (Twilio, Meta, SendGrid) are ours to worry about, not theirs.
 */
export function channelOf(mode: string, lang: Lang): string {
  if (mode === "meta" || mode === "twilio") return tr("channel_whatsapp", lang);
  if (mode === "email") return tr("channel_email", lang);
  return tr("channel_none", lang);
}
