/**
 * Runtime probe: mounts the real App (login page included) into jsdom the way
 * a browser would and reports what ends up in #root, with every console.error
 * captured. Use it when the preview is blank and static checks all pass:
 *
 *     cd web && bun run probe
 *
 * Relative /api fetches are routed to the engine on 127.0.0.1:8000, like the
 * Vite proxy does, so the page reaches the same auth-options answer the
 * browser gets. Anything that unmounts React — a provider throwing on mount,
 * a bad effect — appears here as an UNCAUGHT line with its stack.
 *
 * jsdom cannot run clerk-js (Clerk's browser script), so the hosted card is
 * not exercised here; what this proves is that everything else renders.
 */
process.env.NODE_ENV = "development";

import { JSDOM } from "jsdom";

const dom = new JSDOM(
  '<!doctype html><html lang="en" data-theme="light"><body><div id="root"></div></body></html>',
  { url: "http://localhost:5173/", pretendToBeVisual: true },
);
const g = globalThis as any;
g.window = dom.window;
g.document = dom.window.document;
g.navigator = dom.window.navigator;
g.localStorage = dom.window.localStorage;
g.location = dom.window.location;
// Expose every DOM constructor (HTMLElement, HTMLFormElement, …) the way a
// real browser has them on globalThis — Radix and other UI libs touch them.
for (const key of Object.getOwnPropertyNames(dom.window)) {
  if (!(key in g)) {
    try {
      g[key] = (dom.window as unknown as Record<string, unknown>)[key];
    } catch {
      /* getters that throw outside the realm */
    }
  }
}
g.window.matchMedia = g.window.matchMedia || (() => ({
  matches: false, media: "", addEventListener() {}, removeEventListener() {},
  addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false,
}));
g.ResizeObserver = g.ResizeObserver || class { observe() {} unobserve() {} disconnect() {} };
g.requestAnimationFrame = g.requestAnimationFrame || ((cb: FrameRequestCallback) => setTimeout(() => cb(Date.now()), 16) as unknown as number);
g.cancelAnimationFrame = g.cancelAnimationFrame || ((id: number) => clearTimeout(id as unknown as ReturnType<typeof setTimeout>));

// Route the app's relative /api fetches to the live engine, like the proxy does.
const realFetch = g.fetch.bind(g);
g.fetch = (input: unknown, init?: unknown) => {
  const url = typeof input === "string" ? input : String((input as Request)?.url ?? input);
  const rewritten = url.startsWith("/api") ? `http://127.0.0.1:8000${url}` : url;
  return realFetch(rewritten, init);
};

const React = (await import("react")).default;
const { createRoot } = await import("react-dom/client");

const errors: string[] = [];
const realError = console.error;
console.error = (...a: unknown[]) => {
  errors.push(a.map((x) => (typeof x === "string" ? x : JSON.stringify(x)?.slice(0, 300))).join(" "));
  realError(...a);
};
process.on("uncaughtException", (e) => {
  errors.push("UNCAUGHT: " + ((e as Error)?.stack || String(e)));
});
process.on("unhandledRejection", (e) => {
  errors.push("UNHANDLED REJECTION: " + String(e).slice(0, 500));
});

async function main(): Promise<void> {
  const { default: App } = await import("../src/App");

  const root = createRoot(dom.window.document.getElementById("root")!);
  root.render(React.createElement(React.StrictMode, null, React.createElement(App)));

  // Let async effects settle: auth options, provider discovery, imports.
  await new Promise((r) => setTimeout(r, 12000));

  const html = dom.window.document.getElementById("root")!.innerHTML;
  console.log("root DOM length:", html.length);
  console.log("has login card:", html.includes("Recon-Agent"));
  console.log("has clerk config applied:", html.includes("cl-") || html.toLowerCase().includes("clerk"));
  console.log("--- console.error captured (" + errors.length + ") ---");
  for (const e of errors.slice(0, 10)) console.log("  *", e.slice(0, 600));
  process.exit(html.length > 1000 && errors.length === 0 ? 0 : 1);
}

void main();
