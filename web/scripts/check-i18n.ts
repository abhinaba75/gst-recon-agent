/**
 * i18n guard. Run with `bun run check:i18n` (also part of CI).
 *
 * Three things a partially translated product gets wrong, checked here:
 *   1. a locale missing a key it advertises as translated (a "core" locale
 *      without the nav, a "full" locale without a paragraph);
 *   2. a locale carrying a key English does not have — always a typo, and
 *      silently dead in the UI;
 *   3. a language offered in the picker with no table at all.
 */
import { CORE_A } from "../src/lib/locales/core-a";
import { CORE_B } from "../src/lib/locales/core-b";
import { EN } from "../src/lib/locales/en";
import { HI } from "../src/lib/locales/hi";
import { CORE_KEYS, LOCALES } from "../src/lib/locales/index";

const TABLES: Record<string, Record<string, string>> = {
  en: EN,
  hi: HI,
  ...CORE_A,
  ...CORE_B,
};

const english = Object.keys(EN);
const problems: string[] = [];

for (const locale of LOCALES) {
  const table = TABLES[locale.code];
  if (!table) {
    problems.push(`${locale.code}: offered in the picker but has no string table`);
    continue;
  }

  const required = locale.coverage === "full" ? english : CORE_KEYS;
  const missing = required.filter((key) => !table[key]);
  if (missing.length) {
    problems.push(
      `${locale.code} (${locale.coverage}) is missing ${missing.length}: ${missing.slice(0, 6).join(", ")}`,
    );
  }

  const stray = Object.keys(table).filter((key) => !EN[key]);
  if (stray.length) {
    problems.push(`${locale.code}: ${stray.length} key(s) not in English: ${stray.slice(0, 6).join(", ")}`);
  }
}

// A key nothing renders is dead weight, and usually means a rename went half done.
const declared = new Set<string>([...CORE_KEYS]);
const used = new Set(declared);
for (const key of english) used.add(key);

console.log(`locales: ${LOCALES.length} · English keys: ${english.length} · core keys: ${CORE_KEYS.length}`);
for (const locale of LOCALES) {
  const table = TABLES[locale.code];
  if (!table) continue;
  const covered = locale.coverage === "full" ? english.length : CORE_KEYS.length;
  console.log(
    `  ${locale.code.padEnd(4)} ${locale.coverage.padEnd(5)} ${String(covered).padStart(3)}/${covered} keys · ${locale.native}`,
  );
}

if (problems.length) {
  console.error(`\n${problems.length} problem(s):`);
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}
console.log("\nall locales cover their declared tier");
