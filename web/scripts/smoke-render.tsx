/**
 * Headless render smoke test. Run with `bun run smoke` (also part of CI).
 *
 * `tsc` and `vite build` both pass on an app that throws on first render — a
 * missing provider, a hook outside its context, a bad import. This renders the
 * real component trees to static markup and asserts the pages a user sees,
 * with no browser and no test framework. Without a session the app shows the
 * login page, so both states are checked here.
 *
 * Lazy children (the chart, the assistant) resolve to their fallbacks, which
 * is what a first paint looks like, so this checks the shell.
 */
import { renderToStaticMarkup } from "react-dom/server";

import {
  Assistant,
  AssistantComposer,
  AssistantSuggestions,
} from "../src/components/Assistant";
import { ChartCredit } from "../src/components/chart-credit";
import { PaletteResults, paletteRows } from "../src/components/command-palette";
import { LoginPage, ProviderButtons } from "../src/components/login-page";
import { ClerkSignIn, clerkWorksHere, type ClerkConfig } from "../src/components/clerk-signin";
import { Workspace } from "../src/components/workspace";
import { EN } from "../src/lib/locales/en";
import { providerStartUrl } from "../src/lib/session";
import { getSnapshot } from "../src/lib/snapshot";

const failures: string[] = [];

function check(name: string, ok: boolean, detail = ""): void {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures.push(name);
}

function render(node: React.ReactElement): string {
  try {
    return renderToStaticMarkup(node);
  } catch (error) {
    console.error("render threw:", error);
    process.exit(1);
  }
}

const noop = () => {};
const user = { email: "demo@recon-agent.in", name: "Demo" };
const snapshot = getSnapshot();

console.log("== login page (no session) ==");
const login = render(
  <LoginPage
    lang="en"
    setLang={noop}
    theme="light"
    toggleTheme={noop}
    onSignedIn={noop}
  />,
);
check("login page rendered", login.length > 1000, `${login.length} chars`);
check("asks for both fields", login.includes('id="login-email"') && login.includes('id="login-password"'));
check("password field is masked", login.includes('type="password"'));
check("no figures are shown before signing in", !login.includes("₹1,07,971"));
check("no decorative OAuth buttons", !/Login with (Google|Apple|Meta)/.test(login));
check("skip sign-in is offered", login.includes(EN.login_skip), EN.login_skip);
check("skip note is honest", login.includes(EN.login_skip_note));

// The page mounts the provider buttons only once the engine has answered which
// providers are live, so the buttons are checked directly — with the engine
// saying all three are configured, and with none of them being.
console.log("== social sign-in providers ==");
const offered = ([
  ["google", "Google"],
  ["github", "GitHub"],
  ["apple", "Apple"],
] as const).map(([slug, label]) => ({
  slug,
  label,
  configured: true,
  missing: [] as string[],
  docs: "https://example.invalid",
}));
const providerHtml = render(<ProviderButtons providers={offered} lang="en" />);
check(
  "every live provider gets a button",
  (providerHtml.match(/data-provider=/g) ?? []).length === 3,
  `${(providerHtml.match(/data-provider=/g) ?? []).length} buttons`,
);
check(
  "each button names the provider it starts",
  offered.every((p) => providerHtml.includes(`data-provider="${p.slug}"`)),
);
check(
  "each button carries its provider's own mark",
  (providerHtml.match(/viewBox="0 0 24 24"/g) ?? []).length === 3,
);
check(
  "the buttons say what they do",
  providerHtml.includes("Continue with Google") && providerHtml.includes("Continue with Apple"),
);
check(
  "the buttons are shadcn buttons",
  (providerHtml.match(/data-slot="button"/g) ?? []).length === 3,
);
const unconfigured = render(
  <ProviderButtons
    providers={offered.map((p) => ({ ...p, configured: false, missing: ["RECON_X"] }))}
    lang="en"
  />,
);
check("a provider nobody configured is not offered", unconfigured === "", unconfigured);
check(
  "the start URL carries the page's origin, so the callback can come home",
  providerStartUrl("apple", "https://shop.example") ===
    "/api/auth/apple/start?return_to=https%3A%2F%2Fshop.example",
  providerStartUrl("apple", "https://shop.example"),
);

console.log("== Clerk card: offered only where it can work ==");
const clerkConfig = (origin: string[]): ClerkConfig => ({
  configured: true,
  publishable_key: "pk_test_placeholder",
  issuer: "https://example.clerk.accounts.dev",
  allowed_origins: origin,
  missing: [],
  docs: "https://dashboard.clerk.com",
});
check(
  "an origin the instance allow-listed is offered the card",
  clerkWorksHere(clerkConfig(["https://tax.example"]), "https://tax.example"),
);
check(
  "localhost is offered the card even unlisted (dev instances allow it)",
  clerkWorksHere(clerkConfig([]), "http://localhost:5173"),
);
check(
  "a foreign origin is not offered the card",
  !clerkWorksHere(clerkConfig(["http://localhost:5173"]), "https://preview.example"),
);
check(
  "no location (static render) is offered the card",
  clerkWorksHere(clerkConfig([])),
);
const clerkAbsent = render(
  <ClerkSignIn config={null} lang="en" onSessionToken={noop}>
    <p data-testid="after-clerk">form</p>
  </ClerkSignIn>,
);
check(
  "no Clerk config means no card and the form carries the page",
  clerkAbsent.includes("after-clerk"),
);
const clerkForeign = render(
  <ClerkSignIn
    config={clerkConfig(["http://localhost:5173"])}
    lang="en"
    onSessionToken={noop}
  >
    <p data-testid="after-clerk">form</p>
  </ClerkSignIn>,
);
check(
  "a browser-less render shows loading, not failure, and never mounts the card",
  !clerkForeign.includes("clerk-signin") &&
    clerkForeign.includes("Loading hosted sign-in") &&
    !clerkForeign.includes("Sign-in unavailable"),
);

console.log("== workspace (signed in) ==");
const html = render(
  <Workspace
    lang="en"
    setLang={noop}
    theme="light"
    toggleTheme={noop}
    user={user}
    onSignOut={noop}
  />,
);
const grouped = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const inr = (n: number) => `₹${grouped.format(Math.round(n))}`;

/** How many times a shadcn data-slot appears in the markup. */
const slot = (name: string) => html.split(`data-slot="${name}"`).length - 1;

check("page rendered", html.length > 5000, `${html.length} chars`);
check("brand present", html.includes("Recon-Agent"));
check("sidebar trigger rendered", html.includes('data-slot="sidebar"') || html.includes("sidebar-trigger"));
check("main landmark present", html.includes('id="main"'));
check("skip link is the first interactive element", html.startsWith('<a class="skip-link"'));
check("signed-in operator is named", html.includes(user.email));
check("no stray translation keys", !/>(?:[a-z]+_){1,3}key</.test(html));

console.log("== the four figures, from the snapshot ==");
for (const [key, value] of [
  ["kpi_total", snapshot.totals.total],
  ["kpi_exact", snapshot.totals.exact],
  ["kpi_rescued", snapshot.totals.rescued],
  ["kpi_risk", snapshot.totals.risk],
] as const) {
  check(`${key} shows ${inr(value)}`, html.includes(inr(value)));
  check(`${key} is labelled in English`, html.includes(EN[key]));
}

console.log("== navigation and sections ==");
for (const id of ["top", "submit", "numbers", "compare", "recovery", "ledger", "activity", "glossary", "get-started"]) {
  check(`#${id} is a real target`, html.includes(`id="${id}"`));
}

console.log("== the dashboard shell ==");
check("breadcrumb names the product", html.includes('data-slot="breadcrumb"') && html.includes("Recon-Agent"));
check("panel toggle is a sidebar trigger", html.includes('data-slot="sidebar-trigger"'));
check("dataset switcher is a menu", html.includes('data-slot="dropdown-menu-trigger"'));
check("the switcher names the loaded dataset", html.includes(EN.source_demo), EN.source_demo);
check("search advertises its shortcut", html.includes("⌘K"));
check("the second group is labelled", html.includes(EN.group_reconcile), EN.group_reconcile);
check("nav rows are grouped", slot("sidebar-group-label") >= 1, `${slot("sidebar-group-label")} labels`);
check(
  "ledger's four statuses are collapsible children",
  slot("sidebar-menu-sub-button") === 5,
  `${slot("sidebar-menu-sub-button")} children`,
);
check("recovery row carries a live count", new RegExp(`>${snapshot.counts.missing}<`).test(html));
check("the ledger row reports its open children", html.includes('aria-expanded="true"'));
check(
  "the breadcrumb starts where the reader is",
  html.includes('data-slot="breadcrumb-page"') && html.includes(EN.nav_home),
);

console.log("== the interface is shadcn/ui, not hand-rolled markup ==");
for (const name of [
  "button",
  "badge",
  "card",
  "item",
  "progress",
  "table",
  "toggle-group",
  "toggle-group-item",
  "input",
  "sidebar",
  "sidebar-menu-button",
]) {
  check(`shadcn ${name} is used`, slot(name) > 0, `${slot(name)} on the page`);
}
check("both comparison tables are real tables", slot("table") >= 3, `${slot("table")} tables`);
check("every ledger filter is a toggle", slot("toggle-group-item") === 5);
check("the ledger paginates", slot("pagination") === 1, `${slot("pagination")} paginators`);
check("pagination names both directions", html.includes(EN.page_prev) && html.includes(EN.page_next));
check("search is a shadcn input", html.includes('data-slot="input"'));
check("hero carries a labelled progress bar", html.includes('data-slot="progress"'));
check("no legacy .btn/.pill classes remain", !/class="[^"]*\b(btn|pill|chip|icon-btn|fab)\b/.test(html));

console.log("== the credit chart ==");
// recharts measures its own container; with no layout in a headless render it
// logs a width warning that says nothing about the app, so it is muted here.
const realWarn = console.warn;
console.warn = (() => {}) as typeof console.warn;
const chart = render(<ChartCredit lang="en" />);
console.warn = realWarn;
check("chart renders", chart.length > 500, `${chart.length} chars`);
check("chart has an id", /data-chart="chart-/.test(chart));
check(
  "chart colours come from the theme tokens",
  ["exact", "ai", "missing", "portal_only"].every((s) =>
    chart.includes(`--color-${s}:`),
  ),
);

console.log("== the command palette ==");
// The dialog itself only mounts in a browser, so the list it renders is
// asserted directly: the same component the dialog shows.
const paletteRowsAll = paletteRows("", "en", snapshot);
const palette = render(
  <PaletteResults
    lang="en"
    rows={paletteRowsAll}
    cursor={0}
    onHover={noop}
    onPick={noop}
  />,
);
check("palette is a listbox", palette.includes('role="listbox"'));
check("listbox is labelled", palette.includes(EN.palette_placeholder), EN.palette_placeholder);
check(
  "palette lists every section",
  paletteRowsAll.length === 10 && palette.includes(EN.nav_home) && palette.includes(EN.nav_submit),
  `${paletteRowsAll.length} rows`,
);
check(
  "palette groups sections separately",
  palette.includes(EN.nav_sections) && !palette.includes(EN.ledger_title),
);

const firstSupplier = snapshot.matches[0].supplier_name.slice(0, 5);
const withBills = paletteRows(firstSupplier, "en", snapshot);
check(
  `palette finds bills by supplier ("${firstSupplier}")`,
  withBills.some((row) => row.group === "bill"),
  `${withBills.filter((r) => r.group === "bill").length} bills`,
);
check(
  "palette labels the bill group",
  render(
    <PaletteResults
      lang="en"
      rows={withBills}
      cursor={0}
      onHover={noop}
      onPick={noop}
    />,
  ).includes(EN.ledger_title),
);

const noHits = render(
  <PaletteResults lang="en" rows={[]} cursor={0} onHover={noop} onPick={noop} />,
);
check("palette admits an empty result", noHits.includes(EN.palette_empty), EN.palette_empty);

console.log("== the assistant launcher ==");
const launcher = render(<Assistant lang="en" />);
check("launcher is a shadcn button", launcher.includes('data-slot="button"'));
check("launcher names itself", launcher.includes(EN.asst_launch), EN.asst_launch);
check("launcher reports collapsed state", launcher.includes('aria-expanded="false"'));

console.log("== the assistant's questions ==");
console.log("== the assistant's question box ==");
const composerRef = { current: null } as React.RefObject<HTMLTextAreaElement | null>;
const composer = render(
  <AssistantComposer
    lang="en"
    draft=""
    busy={false}
    source={null}
    inputRef={composerRef}
    inputId="asst-probe"
    onDraft={noop}
    onSend={noop}
  />,
);
check("the question box rides the animated beam", composer.includes("data-beam"));
check(
  "the beam hugs the box's own radius",
  composer.includes("rounded-[20px]"),
);
check(
  "the box is a real labelled textarea",
  composer.includes("<textarea") && composer.includes('id="asst-probe"'),
);
check(
  "send is a round arrow button that says what it does",
  composer.includes(`aria-label="${EN.asst_send}"`) && composer.includes("<svg"),
);
check("the send key is advertised", composer.includes("Enter"));
check(
  "nothing claims a source before an answer exists",
  !composer.includes(EN.asst_source_guide) && !composer.includes(EN.asst_source_model),
);
const answered = render(
  <AssistantComposer
    lang="en"
    draft=""
    busy={false}
    source="guide"
    inputRef={composerRef}
    inputId="asst-probe"
    onDraft={noop}
    onSend={noop}
  />,
);
check(
  "after a guide answer the chip says so",
  answered.includes(EN.asst_source_guide),
  EN.asst_source_guide,
);

const suggestions = render(<AssistantSuggestions lang="en" onPick={noop} />);
check("questions are a questionnaire", suggestions.includes('data-slot="questionnaire"'));
check(
  "four radio choices with a legend",
  (suggestions.split('data-slot="questionnaire-choice"').length - 1) === 4 &&
    suggestions.includes('data-slot="questionnaire-title"'),
);
check("the group is labelled", suggestions.includes(EN.asst_suggest), EN.asst_suggest);

console.log("== the honest bits survive ==");
check("assistant is not in the first paint", !html.includes("assistant-panel"));
check("every ledger row carries evidence", snapshot.matches.every((m) => m.reason.length > 0));

console.log("== the submit section ==");
check("submit section rendered", html.includes('id="submit"'));
check("register file input present", html.includes('id="submit-register"'));
check("portal file input present", html.includes('id="submit-portal"'));
check("file inputs are labelled inputs", html.includes('type="file"'));
check("status region exists", html.includes('id="intake-status"'));
check("sidebar links to submit", html.includes(`>${EN.nav_submit}<`));

console.log();
if (failures.length) {
  console.error(`RESULT: ${failures.length} failure(s): ${failures.join(", ")}`);
  process.exit(1);
}
console.log("RESULT: all checks passed");
