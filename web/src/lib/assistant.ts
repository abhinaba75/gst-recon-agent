import rawGuide from "../data/guide.json";
import { getSnapshot } from "./snapshot";

/**
 * The assistant's answers come from the engine when it is running, and from
 * the same guide file when it is not — which is the situation on a static
 * deploy. The guide is a single shared file rather than copy-pasted prose, so
 * the browser and the Python engine cannot drift apart.
 */

export interface AssistantReply {
  ok: boolean;
  answer: string;
  /** "model" — a language model wrote it; "guide" — the built-in guide did. */
  source: "model" | "guide" | "none";
  topic?: string;
  model?: string;
}

interface GuideEntry {
  id: string;
  keywords: string[];
  en: string;
  hi?: string;
  [lang: string]: unknown;
}

const ENTRIES = (rawGuide as { entries: GuideEntry[] }).entries;

const NO_ANSWER: Record<string, string> = {
  en: "I do not have that in the built-in guide. Try asking about the four figures, a supplier status, Rule 88D, or how to send a recovery notice.",
  hi: "यह बिल्ट-इन गाइड में नहीं है। चार आँकड़ों, किसी विक्रेता की स्थिति, Rule 88D, या रिकवरी नोटिस भेजने के बारे में पूछें।",
};

const GROUPED = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

function inr(amount: number): string {
  return `₹${GROUPED.format(Math.round(amount))}`;
}

/** Facts the guide's {{placeholders}} resolve to — the page's own figures. */
function facts(): Record<string, string> {
  const { totals, counts, period } = getSnapshot();
  return {
    period,
    bills: String(counts.books),
    portal: String(counts.portal),
    missing_count: String(counts.missing),
    recovered_count: String(counts.rescued),
    total: inr(totals.total),
    rescued: inr(totals.rescued),
    risk: inr(totals.risk),
    write_off: inr(totals.write_off),
  };
}

function render(text: string): string {
  const f = facts();
  return text.replace(/\{\{(\w+)\}\}/g, (whole, key: string) => f[key] ?? whole);
}

/** Score by keyword length, so "rule 88d" beats a generic "notice". */
export function matchGuide(question: string): GuideEntry | null {
  const text = question.toLowerCase();
  let best: GuideEntry | null = null;
  let bestScore = 0;
  for (const entry of ENTRIES) {
    const score = entry.keywords.reduce(
      (sum, k) => (text.includes(k.toLowerCase()) ? sum + k.length : sum),
      0,
    );
    if (score > bestScore) {
      best = entry;
      bestScore = score;
    }
  }
  return best;
}

export function localAnswer(question: string, lang: string): AssistantReply {
  const entry = matchGuide(question);
  if (!entry) {
    return { ok: false, source: "none", answer: NO_ANSWER[lang] ?? NO_ANSWER.en };
  }
  const text = (entry[lang] as string | undefined) ?? entry.en;
  return { ok: true, source: "guide", topic: entry.id, answer: render(text) };
}

export async function askAssistant(
  question: string,
  lang: string,
): Promise<AssistantReply> {
  try {
    const res = await fetch("/api/assistant", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, lang }),
    });
    if (res.ok) {
      const body = (await res.json()) as AssistantReply;
      if (body && typeof body.answer === "string" && body.answer) return body;
    }
  } catch {
    /* no engine reachable — answer from the shared guide */
  }
  return localAnswer(question, lang);
}
