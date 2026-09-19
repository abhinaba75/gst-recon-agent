/**
 * Session handling.
 *
 * The token is opaque and the engine decides whether it is still valid, so the
 * browser never holds anything it could forge. It lives in `sessionStorage`,
 * not `localStorage`: closing the tab ends the session, which is what an
 * operator on a shared shop computer would expect.
 */

export interface SessionUser {
  email: string;
  name: string;
  /** How this account signs in: password, google, github, operator, demo. */
  provider?: string;
  created_at?: string;
  last_login_at?: string;
}

export interface Session {
  token: string;
  user: SessionUser;
  /** "offline" means this browser admitted itself; the server verified nothing. */
  mode: "demo" | "configured" | "offline";
  /** Which door was used: the operator account, a user account, the demo pair. */
  source?: "operator" | "account" | "demo" | "offline";
}

/** One social sign-in the deployment has actually configured. */
export interface ProviderOption {
  slug: string;
  label: string;
  configured: boolean;
  missing: string[];
  docs: string;
}

/** What the login page may offer, as the engine reports it. */
export interface AuthOptions {
  login_mode: "demo" | "configured";
  password: boolean;
  signup_open: boolean;
  account_store: string;
  accounts: number;
  demo: boolean;
  demo_email: string | null;
  demo_password: string | null;
  providers: ProviderOption[];
  /** The hosted sign-in, present when the engine is new enough to report it. */
  clerk?: {
    configured: boolean;
    publishable_key: string | null;
    issuer: string | null;
    allowed_origins: string[];
    missing: string[];
    docs: string;
  };
}

const KEY = "recon-session";

/**
 * The documented demo pair, used only when there is no engine to ask. A
 * static deploy (no FastAPI behind it) would otherwise be a login page nobody
 * can pass. It still only accepts the published demo credentials, and the
 * workspace says plainly that the session was not verified.
 */
const OFFLINE_DEMO = { email: "demo@recon-agent.in", password: "demo-88d" };

export function readSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    return parsed?.token && parsed?.user ? parsed : null;
  } catch {
    return null;
  }
}

function writeSession(session: Session | null): void {
  try {
    if (session) window.sessionStorage.setItem(KEY, JSON.stringify(session));
    else window.sessionStorage.removeItem(KEY);
  } catch {
    /* storage blocked — the session applies to this page only */
  }
}

export interface SignInResult {
  ok: boolean;
  session?: Session;
  detail?: string;
}

/**
 * The published demo pair, accepted only when no engine can be asked. Still
 * only that pair — an offline login that took any password would be a lie.
 */
function offlineDemo(email: string, password: string): SignInResult {
  const clean = email.trim().toLowerCase();
  if (clean !== OFFLINE_DEMO.email || password !== OFFLINE_DEMO.password) {
    return { ok: false, detail: "offline" };
  }
  const session = offlineSession();
  return { ok: true, session };
}

/**
 * Admit the published demo pair without asking the engine, and mark the
 * session `offline` so the workspace says so in its red banner. Used by the
 * temporary skip-sign-in path on the login page — never by real sign-in.
 */
export function offlineSession(): Session {
  const session: Session = {
    token: "offline-demo",
    user: { email: OFFLINE_DEMO.email, name: "Demo", provider: "demo" },
    mode: "offline",
    source: "offline",
  };
  writeSession(session);
  return session;
}

export async function signIn(email: string, password: string): Promise<SignInResult> {
  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (res.status === 404 || res.status === 405) {
      // No login endpoint at all: a static deploy. Fall through to the
      // documented offline path rather than dead-ending the page.
      return offlineDemo(email, password);
    }
    if (!res.ok) {
      return { ok: false, detail: "The engine answered with an error." };
    }
    const body = (await res.json()) as {
      ok: boolean;
      token?: string;
      user?: SessionUser;
      mode?: "demo" | "configured";
      source?: Session["source"];
      detail?: string;
    };
    if (!body.ok || !body.token || !body.user) {
      return { ok: false, detail: body.detail };
    }
    const session: Session = {
      token: body.token,
      user: body.user,
      mode: body.mode ?? "demo",
      source: body.source ?? "demo",
    };
    writeSession(session);
    return { ok: true, session };
  } catch {
    return offlineDemo(email, password);
  }
}

/**
 * What this deployment can offer, straight from the engine. `null` means the
 * engine could not be asked — the page then offers the password form and says
 * plainly that sign-in cannot be verified, rather than inventing buttons.
 */
export async function authOptions(): Promise<AuthOptions | null> {
  try {
    const res = await fetch("/api/auth/options", { headers: { accept: "application/json" } });
    if (!res.ok) return null;
    return (await res.json()) as AuthOptions;
  } catch {
    return null;
  }
}

/** Create an account on this deployment and sign it in. */
export async function register(
  name: string,
  email: string,
  password: string,
): Promise<SignInResult> {
  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    const body = (await res.json()) as {
      ok: boolean;
      token?: string;
      user?: SessionUser;
      mode?: "demo" | "configured";
      source?: Session["source"];
      detail?: string;
    };
    if (!body.ok || !body.token || !body.user) {
      return { ok: false, detail: body.detail };
    }
    const session: Session = {
      token: body.token,
      user: body.user,
      mode: body.mode ?? "demo",
      source: body.source ?? "account",
    };
    writeSession(session);
    return { ok: true, session };
  } catch {
    return { ok: false, detail: "offline" };
  }
}

/**
 * Where the browser goes to start a social sign-in. The engine checks the
 * destination against this deployment's own origin, so the `return_to` here is
 * a hint rather than an open redirect.
 *
 * The origin is a parameter rather than a direct read of `window.location` so
 * the URL can be checked without a browser. A deployment whose page is served
 * by a proxy that rewrites `Host` — the Vite dev server does — has to list that
 * origin in `RECON_ALLOWED_ORIGINS`, or the engine answers on its own address
 * and the callback never reaches the page.
 */
export function providerStartUrl(slug: string, origin?: string): string {
  const from = origin ?? (typeof window === "undefined" ? "" : window.location.origin);
  return `/api/auth/${slug}/start?return_to=${encodeURIComponent(from)}`;
}

/**
 * Swap a verified Clerk session token for this deployment's session.
 *
 * The engine checks the token against Clerk's own signing keys, the issuer it
 * was configured with and the origins it allows, then reads the profile from
 * Clerk's Backend API — so the browser never decides who it is. A refusal is
 * the engine's own sentence, shown as-is on the sign-in card.
 */
export async function exchangeClerkToken(token: string): Promise<SignInResult> {
  try {
    const res = await fetch("/api/auth/clerk", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token }),
    });
    const body = (await res.json()) as {
      ok: boolean;
      token?: string;
      user?: SessionUser;
      mode?: "demo" | "configured";
      source?: Session["source"];
      detail?: string;
    };
    if (!body.ok || !body.token || !body.user) {
      return { ok: false, detail: body.detail };
    }
    const session: Session = {
      token: body.token,
      user: body.user,
      mode: body.mode ?? "demo",
      source: body.source ?? "account",
    };
    writeSession(session);
    return { ok: true, session };
  } catch {
    return { ok: false, detail: "offline" };
  }
}

/**
 * Swap the callback's one-time code for the session, once. The token is never
 * in the URL the provider sent us back to.
 */
export async function exchangeAuthCode(code: string): Promise<SignInResult> {
  try {
    const res = await fetch("/api/auth/exchange", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const body = (await res.json()) as {
      ok: boolean;
      token?: string;
      user?: SessionUser;
      mode?: "demo" | "configured";
      source?: Session["source"];
      detail?: string;
    };
    if (!body.ok || !body.token || !body.user) {
      return { ok: false, detail: body.detail };
    }
    const session: Session = {
      token: body.token,
      user: body.user,
      mode: body.mode ?? "demo",
      source: body.source ?? "account",
    };
    writeSession(session);
    return { ok: true, session };
  } catch {
    return { ok: false, detail: "offline" };
  }
}

/** The account behind a live token, as the engine sees it. */
export async function profile(session: Session): Promise<SessionUser | null> {
  try {
    const res = await fetch("/api/me", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token: session.token }),
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { ok: boolean; user?: SessionUser };
    return body.ok && body.user ? body.user : null;
  } catch {
    return null;
  }
}

export async function signOut(session: Session | null): Promise<void> {
  writeSession(null);
  if (!session) return;
  try {
    await fetch("/api/logout", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token: session.token }),
    });
  } catch {
    /* the local session is already gone, which is the part that matters */
  }
}

/** Confirm the stored token is still live when the page loads. */
export async function stillValid(session: Session): Promise<boolean> {
  try {
    const res = await fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token: session.token }),
    });
    if (!res.ok) return true; // no session endpoint: keep the local session
    const body = (await res.json()) as { ok: boolean };
    return body.ok;
  } catch {
    return true; // engine unreachable: do not sign the operator out
  }
}
