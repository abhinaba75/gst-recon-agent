import { useEffect, useState } from "react";

import { LoginPage } from "./components/login-page";
import { Workspace } from "./components/workspace";
import { LANG_STORAGE_KEY, LOCALES, initialLang, type Lang } from "./lib/i18n";
import { readSession, signOut, stillValid, type Session } from "./lib/session";
import { useTheme } from "./lib/theme";

/**
 * The gate: a session, or the login page.
 *
 * The token is only a claim until the engine confirms it, so a stored session
 * is revalidated on load — an engine restart clears its sessions, and the
 * browser should not keep showing a workspace the server has forgotten.
 */
/**
 * What a sign-in provider handed back, read once on load.
 *
 * The callback never puts a session token in a URL, so what arrives here is a
 * one-time code — and the code is stripped from the address bar immediately, so
 * a reload cannot replay it and a copied link cannot carry it.
 */
function readAuthHandoff(): { code: string | null; error: string | null } {
  if (typeof window === "undefined") return { code: null, error: null };
  const params = new URLSearchParams(window.location.search);
  return { code: params.get("auth_code"), error: params.get("auth_error") };
}

export default function App() {
  const { theme, toggle } = useTheme();
  const [lang, setLang] = useState<Lang>(initialLang);
  const [session, setSession] = useState<Session | null>(readSession);
  const [handoff] = useState(readAuthHandoff);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!handoff.code && !handoff.error) return;
    window.history.replaceState({}, "", window.location.pathname);
  }, [handoff]);

  // Reading direction and hyphenation follow the chosen language, and the
  // choice survives a reload — a reader should not have to pick twice.
  useEffect(() => {
    const meta = LOCALES.find((l) => l.code === lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = meta?.dir ?? "ltr";
    try {
      window.localStorage.setItem(LANG_STORAGE_KEY, lang);
    } catch {
      /* the choice still applies for this session */
    }
  }, [lang]);

  useEffect(() => {
    const stored = readSession();
    if (!stored) return;
    let alive = true;
    void stillValid(stored).then((ok) => {
      if (!alive || ok) return;
      void signOut(stored);
      setSession(null);
    });
    return () => {
      alive = false;
    };
  }, []);

  if (!session) {
    return (
      <LoginPage
        lang={lang}
        setLang={setLang}
        theme={theme}
        toggleTheme={toggle}
        onSignedIn={setSession}
        initialError={handoff.error}
        authCode={handoff.code}
      />
    );
  }

  return (
    <Workspace
      lang={lang}
      setLang={setLang}
      theme={theme}
      toggleTheme={toggle}
      user={session.user}
      unverified={session.mode === "offline"}
      onSignOut={() => {
        void signOut(session);
        setSession(null);
      }}
    />
  );
}
