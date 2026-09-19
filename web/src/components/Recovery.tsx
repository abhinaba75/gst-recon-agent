import { useState } from "react";
import { CheckCircle2Icon, SendIcon, TriangleAlertIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemTitle,
} from "@/components/ui/item";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { dispatch } from "../lib/api";
import { inr } from "../lib/format";
import { alt, channelOf, tr, type Lang } from "../lib/i18n";
import { recoveryOf, useSnapshot } from "../lib/snapshot";
import type { ActivityEvent, DispatchResult, MatchRow } from "../lib/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  HoverInfo,
  SectionHead,
  Stamp,
} from "./ui";

/** A fresh deliberate-confirmation code for one dispatch. */
function newCode(): string {
  return String(Math.floor(100000 + Math.random() * 900000));
}

/**
 * The A2A recovery notices. Each supplier is a shadcn Item with its own
 * dispatch action, and the confirmation dialog is a Dialog with a read-only
 * Textarea of the message, a six-digit deliberate confirmation, and an Alert
 * reporting exactly what the engine did next.
 */
export function Recovery({
  lang,
  onEvent,
}: {
  lang: Lang;
  onEvent: (event: ActivityEvent) => void;
}) {
  const snapshot = useSnapshot();
  const recovery = recoveryOf(snapshot);

  const [active, setActive] = useState<MatchRow | null>(null);
  const [result, setResult] = useState<DispatchResult | null>(null);
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState(false);
  const [code, setCode] = useState("");
  const [typed, setTyped] = useState("");

  async function confirm(row: MatchRow) {
    setSending(true);
    const res = await dispatch({
      period: snapshot.period,
      invoiceNo: row.register_no,
      supplier: row.supplier_name,
      message: row.message,
      phone: row.phone,
      email: row.email,
    });
    setResult(res);
    setSending(false);
    onEvent({
      at: new Date().toISOString().slice(11, 19),
      tag: "A2A",
      text: res.ok
        ? `Recovery notice for ${row.register_no} sent to ${row.supplier_name} by ${channelOf(res.mode, lang)}`
        : `Recovery notice for ${row.register_no} was not sent — ${res.detail}`,
    });
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2400);
    } catch {
      setCopied(false);
    }
  }

  function open(row: MatchRow) {
    setResult(null);
    setCopied(false);
    setTyped("");
    setCode(newCode());
    setActive(row);
    onEvent({
      at: new Date().toISOString().slice(11, 19),
      tag: "A2A",
      text: `Recovery notice opened for ${row.register_no} · ${row.supplier_name}`,
    });
  }

  const close = () => {
    setActive(null);
    setResult(null);
    setTyped("");
  };

  return (
    <section id="recovery" className="border-border scroll-mt-6 border-t">
      <div className="shell py-14">
        <SectionHead
          id="recovery-title"
          titleKey="recovery_title"
          subKey="recovery_body"
          lang={lang}
        />

        <Card className="mb-5">
          <CardContent className="flex flex-col gap-1">
            <p className="text-muted-foreground text-[0.9rem]">{tr("recovery_sub", lang)}</p>
            <p className="text-neg font-mono text-[1.7rem] tabular-nums">
              {inr(snapshot.totals.risk)}
            </p>
            <p className="text-muted-foreground flex items-center gap-1.5 text-[0.85rem]">
              <Badge variant="outline">{recovery.length}</Badge>
              {tr("col_books", lang)} · {tr("kpi_rule88d", lang)}
              <HoverInfo label={tr("hover_rule88d_label", lang)}>
                {tr("hover_rule88d", lang)}
              </HoverInfo>
            </p>
          </CardContent>
        </Card>

        <ItemGroup className="gap-3">
          {recovery.map((row) => {
            const contact = row.phone || row.email;
            return (
              <Item
                key={row.register_no}
                role="listitem"
                variant="outline"
                className="flex-wrap items-start gap-x-5 gap-y-3 rounded-xl p-5 shadow-xs"
              >
                <ItemContent className="min-w-[16rem] gap-1">
                  <ItemTitle className="flex-wrap gap-2 text-base">
                    <Stamp status="missing" lang={lang} />
                    {row.supplier_name}
                    <HoverInfo label={tr("hover_supplier_label", lang)}>
                      <span className="block font-medium">{row.supplier_name}</span>
                      <span className="text-muted-foreground mt-1 block" translate="no">
                        {row.supplier_gstin}
                      </span>
                      <span className="mt-2 block">{tr("hover_supplier", lang)}</span>
                    </HoverInfo>
                  </ItemTitle>
                  <ItemDescription className="line-clamp-none text-[0.85rem]">
                    <code translate="no">{row.register_no}</code> ·{" "}
                    <span className="font-mono tabular-nums">{inr(row.tax)}</span> ·{" "}
                    <span translate="no">{row.supplier_gstin}</span>
                  </ItemDescription>
                  <ItemDescription className="line-clamp-none text-[0.82rem]">
                    {contact || tr("no_contact", lang)}
                    {row.email && row.phone ? ` · ${row.email}` : ""}
                  </ItemDescription>
                </ItemContent>
                <ItemActions className="w-full sm:w-auto">
                  <Button
                    className="min-h-11 w-full sm:w-auto"
                    disabled={!contact}
                    title={contact ? undefined : tr("no_contact", lang)}
                    onClick={() => open(row)}
                  >
                    <SendIcon aria-hidden="true" />
                    {tr("dispatch", lang)}
                  </Button>
                </ItemActions>
              </Item>
            );
          })}
        </ItemGroup>
      </div>

      <Dialog
        open={active !== null}
        onOpenChange={(next) => {
          if (!next) close();
        }}
      >
        <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{tr("dialog_title", lang)}</DialogTitle>
            <DialogDescription>{tr("dialog_sub", lang)}</DialogDescription>
          </DialogHeader>

          {active && (
            <div className="flex flex-col gap-4">
              <ItemGroup className="grid gap-3 sm:grid-cols-2">
                <Item
                  role="listitem"
                  variant="muted"
                  size="sm"
                  className="flex-col items-start gap-1"
                >
                  <ItemContent>
                    <Label className="text-muted-foreground text-[0.82rem]">
                      {tr("dialog_to", lang)}
                    </Label>
                    <div className="mt-0.5">
                      {active.supplier_name}
                      <span
                        className="text-muted-foreground block font-mono text-[0.82rem]"
                        translate="no"
                      >
                        {active.phone || active.email}
                      </span>
                    </div>
                  </ItemContent>
                </Item>
                <Item
                  role="listitem"
                  variant="muted"
                  size="sm"
                  className="flex-col items-start gap-1"
                >
                  <ItemContent>
                    <Label className="text-muted-foreground text-[0.82rem]">
                      {tr("dialog_period", lang)}
                    </Label>
                    <div className="mt-0.5">
                      {snapshot.period}
                      <span
                        className="text-muted-foreground block font-mono text-[0.82rem]"
                        translate="no"
                      >
                        {snapshot.fp}
                      </span>
                    </div>
                  </ItemContent>
                </Item>
              </ItemGroup>

              <div className="flex flex-col gap-1">
                <Label htmlFor="dispatch-message" className="text-muted-foreground text-[0.82rem]">
                  {tr("dialog_message", lang)}
                </Label>
                <Textarea
                  id="dispatch-message"
                  readOnly
                  rows={5}
                  value={active.message}
                  className="text-[0.9rem] leading-relaxed"
                />
                {alt("dialog_message", lang) && (
                  <p className="text-muted-foreground text-[0.82rem]" lang="en">
                    {alt("dialog_message", lang)}
                  </p>
                )}
              </div>

              <Alert>
                <TriangleAlertIcon aria-hidden="true" />
                <AlertTitle>{tr("kpi_rule88d", lang)}</AlertTitle>
                <AlertDescription>
                  {tr("dialog_exposure", lang)}{" "}
                  <span className="text-neg font-mono tabular-nums">
                    {inr(active.tax * 0.24)}
                  </span>
                </AlertDescription>
              </Alert>

              {/* One deliberate action before an irreversible send. */}
              <Card className="gap-2 py-3">
                <CardContent className="flex flex-col gap-2">
                  <Label htmlFor="dispatch-confirm" className="text-[0.85rem]">
                    {tr("confirm_prompt", lang)}{" "}
                    <Badge
                      variant="secondary"
                      className="font-mono tabular-nums"
                      translate="no"
                    >
                      {code}
                    </Badge>
                  </Label>
                  <InputOTP
                    id="dispatch-confirm"
                    maxLength={6}
                    value={typed}
                    onChange={setTyped}
                    inputMode="numeric"
                    containerClassName="justify-start"
                  >
                    <InputOTPGroup>
                      {[0, 1, 2, 3, 4, 5].map((i) => (
                        <InputOTPSlot key={i} index={i} />
                      ))}
                    </InputOTPGroup>
                  </InputOTP>
                  <p className="text-muted-foreground text-[0.78rem] leading-relaxed">
                    {tr("confirm_note", lang)}
                  </p>
                </CardContent>
              </Card>

              {result && (
                <Alert
                  role="status"
                  aria-live="polite"
                  variant={result.ok ? "default" : "destructive"}
                >
                  {result.ok ? (
                    <CheckCircle2Icon className="text-pos" aria-hidden="true" />
                  ) : (
                    <TriangleAlertIcon aria-hidden="true" />
                  )}
                  <AlertTitle>
                    {result.ok
                      ? `${tr("sent", lang)} · ${channelOf(result.mode, lang)}`
                      : tr("not_sent", lang)}
                  </AlertTitle>
                  <AlertDescription>
                    {result.ok ? tr("sent_note", lang) : result.detail}
                  </AlertDescription>
                </Alert>
              )}

              <Separator />

              <DialogFooter className="flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-start">
                <Button
                  className="min-h-11 w-full sm:w-auto"
                  disabled={sending || typed !== code}
                  aria-busy={sending}
                  onClick={() => confirm(active)}
                >
                  {sending ? (
                    <>
                      <Spinner className="text-current" />
                      {tr("sending", lang)}
                    </>
                  ) : (
                    tr("confirm", lang)
                  )}
                </Button>
                <Button
                  variant="ghost"
                  className="min-h-11 w-full sm:w-auto"
                  onClick={() => copy(active.message)}
                >
                  {copied ? tr("copied", lang) : tr("copy_message", lang)}
                </Button>
              </DialogFooter>
              <p className="text-muted-foreground text-[0.8rem]">{tr("dialog_footer", lang)}</p>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
