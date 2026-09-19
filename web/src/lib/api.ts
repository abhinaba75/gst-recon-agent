import type { DispatchResult, Snapshot } from "./types";

/**
 * The Python engine serves /api when it is running. When it is not — a static
 * build, a judge's laptop, a preview environment with no backend — the page
 * still renders the snapshot, and the dispatch dialog says plainly that
 * nothing was sent. A fabricated "delivered" is the one outcome the product
 * must never produce, so this client only ever reports what it actually did.
 */

export interface DispatchRequest {
  period: string;
  invoiceNo: string;
  supplier: string;
  message: string;
  phone: string;
  email: string;
}

export async function dispatch(request: DispatchRequest): Promise<DispatchResult> {
  try {
    const res = await fetch("/api/dispatch", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    });
    if (res.ok) {
      const body = (await res.json()) as {
        ok: boolean;
        mode: string;
        detail: string;
        message_id?: string | null;
      };
      return {
        ok: body.ok,
        mode: body.mode,
        detail: body.detail,
        messageId: body.message_id ?? null,
      };
    }
    if (res.status !== 404 && res.status !== 405) {
      return {
        ok: false,
        mode: "error",
        detail: `The messaging service could not be reached (error ${res.status}).`,
        messageId: null,
      };
    }
  } catch {
    /* no backend reachable — fall through to the static report */
  }
  return {
    ok: false,
    mode: "static",
    detail:
      "Nothing was sent: this page is running without a live messaging channel " +
      "connected. The text above is exactly what the supplier would receive.",
    messageId: null,
  };
}

export interface IntakeResult {
  ok: boolean;
  snapshot?: Snapshot;
  /** One sentence naming what the engine did, shown next to the result. */
  detail?: string;
  /** Non-fatal problems, e.g. a row the engine could not read at all. */
  warnings?: string[];
}

export interface IntakeFiles {
  register: File | null;
  portal: File | null;
}

/**
 * Submit a purchase register and a GSTR-2B file for reconciliation.
 *
 * The files go straight to the engine, which reads them in memory — nothing is
 * written to disk and nothing is kept, so the page can say that and mean it.
 * A missing file is not an error: with neither file supplied the engine runs
 * the bundled sample documents, which is the one-click path for a visitor who
 * has no GST data of their own.
 */
export async function intake(files: IntakeFiles): Promise<IntakeResult> {
  const body = new FormData();
  if (files.register) body.append("register", files.register);
  if (files.portal) body.append("portal", files.portal);

  let res: Response;
  try {
    res = await fetch("/api/intake", { method: "POST", body });
  } catch {
    return {
      ok: false,
      detail:
        "The reconciliation engine is not reachable from this page, so nothing was processed. " +
        "Start the app with its engine running and try again.",
    };
  }

  if (res.status === 404 || res.status === 405) {
    return {
      ok: false,
      detail:
        "This page is running without a reconciliation engine, so the documents could not be read.",
    };
  }

  let parsed: {
    ok?: boolean;
    snapshot?: Snapshot;
    detail?: string;
    warnings?: string[];
  };
  try {
    parsed = (await res.json()) as typeof parsed;
  } catch {
    return { ok: false, detail: `The engine answered with an error (${res.status}).` };
  }

  if (!parsed.ok || !parsed.snapshot) {
    return {
      ok: false,
      detail: parsed.detail ?? `The engine could not read those documents (${res.status}).`,
    };
  }

  return { ok: true, snapshot: parsed.snapshot, warnings: parsed.warnings ?? [] };
}
