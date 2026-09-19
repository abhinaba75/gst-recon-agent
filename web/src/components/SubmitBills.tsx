import { useRef, useState } from "react";
import {
  CircleCheckIcon,
  FileJsonIcon,
  FileSpreadsheetIcon,
  RotateCcwIcon,
  TriangleAlertIcon,
  UploadIcon,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { Card, CardContent } from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import {
  Item,
  ItemDescription,
  ItemFooter,
  ItemGroup,
} from "@/components/ui/item";
import { Spinner } from "@/components/ui/spinner";
import { intake, type IntakeResult } from "../lib/api";
import { alt, tr, type Lang } from "../lib/i18n";
import { resetSnapshot, setSnapshot, showingDemo, useSnapshot } from "../lib/snapshot";
import { HoverInfo, SectionHead } from "./ui";

/**
 * Where the operator's own documents enter the product.
 *
 * The reconciliation itself is deliberately not reimplemented here: the two
 * files go to `POST /api/intake`, which answers with a snapshot built by the
 * very same engine that exported the bundled demo. The figures on every other
 * section of this page then re-render from that snapshot — a submitted run is
 * first-class, not a side widget.
 *
 * Honesty rules the failure paths: whatever the engine could not read is shown
 * as its sentence, in an Alert beside the button, and the old figures stay on
 * screen until a new snapshot has actually replaced them.
 */
export function SubmitBills({ lang }: { lang: Lang }) {
  const snapshot = useSnapshot();
  const demo = showingDemo();

  const [registerName, setRegisterName] = useState("");
  const [portalName, setPortalName] = useState("");
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<IntakeResult | null>(null);

  const registerInput = useRef<HTMLInputElement>(null);
  const portalInput = useRef<HTMLInputElement>(null);

  const hasOwnFiles = registerName !== "" || portalName !== "";

  async function run() {
    if (busy) return;
    setBusy(true);
    setOutcome(null);
    const files = {
      register: registerInput.current?.files?.[0] ?? null,
      portal: portalInput.current?.files?.[0] ?? null,
    };
    const result = await intake(files);
    setOutcome(result);
    if (result.ok && result.snapshot) {
      setSnapshot(result.snapshot, false);
    }
    setBusy(false);
  }

  function clearFile(which: "register" | "portal") {
    const input = which === "register" ? registerInput : portalInput;
    if (input.current) input.current.value = "";
    if (which === "register") setRegisterName("");
    else setPortalName("");
  }

  function reset() {
    resetSnapshot();
    clearFile("register");
    clearFile("portal");
    setOutcome(null);
  }

  const english = alt("submit_title", lang);
  const ariaId = "intake-status";

  return (
    <section id="submit" className="border-border scroll-mt-20 border-b">
      <div className="shell py-12 md:py-14">
        <SectionHead id="submit-title" titleKey="submit_title" subKey="submit_sub" lang={lang} />

        {english && (
          <p className="text-muted-foreground -mt-4 mb-6 text-[0.95rem]" lang="en">
            {english}
          </p>
        )}

        <Card>
          <CardContent className="flex flex-col gap-5">
            <p className="prose-note text-muted-foreground text-[0.98rem]">
              {tr("submit_body", lang)}
            </p>

            <ItemGroup className="grid gap-4 md:grid-cols-2">
              {/* The books: the register the accountant already keeps. */}
              <Item
                role="listitem"
                variant="outline"
                className="flex-col items-stretch gap-2 p-4"
              >
                <Field className="gap-1">
                  <FieldLabel asChild>
                    <span className="flex items-center gap-2">
                      <FileSpreadsheetIcon
                        aria-hidden="true"
                        className="text-primary size-5"
                      />
                      {tr("submit_register_label", lang)}
                      <HoverInfo label={tr("submit_register_label", lang)}>
                        {tr("submit_register_hint", lang)}
                      </HoverInfo>
                    </span>
                  </FieldLabel>
                  <FieldDescription className="text-[0.85rem]">
                    {tr("submit_register_hint", lang)}
                  </FieldDescription>
                </Field>

                <input
                  ref={registerInput}
                  type="file"
                  id="submit-register"
                  accept=".xlsx,.xls,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  className="sr-only"
                  onChange={(e) => setRegisterName(e.target.files?.[0]?.name ?? "")}
                />
                <ItemFooter className="justify-start gap-2">
                  <Button
                    variant="outline"
                    className="min-h-11"
                    onClick={() => registerInput.current?.click()}
                  >
                    {registerName ? tr("submit_change", lang) : tr("submit_choose", lang)}
                  </Button>
                  {registerName && (
                    <Button
                      variant="ghost"
                      className="text-muted-foreground min-h-11"
                      onClick={() => clearFile("register")}
                    >
                      {tr("submit_clear", lang)}
                    </Button>
                  )}
                </ItemFooter>
                <ItemDescription
                  className="line-clamp-none font-mono text-[0.82rem]"
                  aria-live="polite"
                >
                  {registerName
                    ? `${tr("submit_selected", lang)}: ${registerName}`
                    : tr("submit_none", lang)}
                </ItemDescription>
              </Item>

              {/* The portal: what the government says is claimable. */}
              <Item
                role="listitem"
                variant="outline"
                className="flex-col items-stretch gap-2 p-4"
              >
                <Field className="gap-1">
                  <FieldLabel asChild>
                    <span className="flex items-center gap-2">
                      <FileJsonIcon aria-hidden="true" className="text-primary size-5" />
                      {tr("submit_portal_label", lang)}
                      <HoverInfo label={tr("submit_portal_label", lang)}>
                        {tr("submit_portal_hint", lang)}
                      </HoverInfo>
                    </span>
                  </FieldLabel>
                  <FieldDescription className="text-[0.85rem]">
                    {tr("submit_portal_hint", lang)}
                  </FieldDescription>
                </Field>

                <input
                  ref={portalInput}
                  type="file"
                  id="submit-portal"
                  accept=".json,application/json"
                  className="sr-only"
                  onChange={(e) => setPortalName(e.target.files?.[0]?.name ?? "")}
                />
                <ItemFooter className="justify-start gap-2">
                  <Button
                    variant="outline"
                    className="min-h-11"
                    onClick={() => portalInput.current?.click()}
                  >
                    {portalName ? tr("submit_change", lang) : tr("submit_choose", lang)}
                  </Button>
                  {portalName && (
                    <Button
                      variant="ghost"
                      className="text-muted-foreground min-h-11"
                      onClick={() => clearFile("portal")}
                    >
                      {tr("submit_clear", lang)}
                    </Button>
                  )}
                </ItemFooter>
                <ItemDescription
                  className="line-clamp-none font-mono text-[0.82rem]"
                  aria-live="polite"
                >
                  {portalName
                    ? `${tr("submit_selected", lang)}: ${portalName}`
                    : tr("submit_none", lang)}
                </ItemDescription>
              </Item>
            </ItemGroup>

            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
              <ButtonGroup className="w-full flex-col gap-3 sm:w-auto sm:flex-row sm:gap-0">
                <Button
                  size="lg"
                  className="min-h-11 w-full sm:w-auto"
                  aria-busy={busy}
                  onClick={() => void run()}
                >
                  {busy ? (
                    <>
                      <Spinner className="text-current" />
                      {tr("submit_busy", lang)}
                    </>
                  ) : (
                    <>
                      <UploadIcon aria-hidden="true" />
                      {hasOwnFiles ? tr("submit_run", lang) : tr("submit_demo_run", lang)}
                    </>
                  )}
                </Button>

                {!demo && (
                  <Button
                    variant="outline"
                    size="lg"
                    className="min-h-11 w-full sm:w-auto"
                    onClick={reset}
                  >
                    <RotateCcwIcon aria-hidden="true" />
                    {tr("submit_reset", lang)}
                  </Button>
                )}
              </ButtonGroup>

              <p className="text-muted-foreground text-[0.82rem]">
                {tr("submit_privacy", lang)}
              </p>
            </div>

            {/* One status region: what the engine actually answered, in its words. */}
            <div id={ariaId} role="status" aria-live="polite" className="flex flex-col gap-2">
              {outcome && !outcome.ok && (
                <Alert variant="destructive">
                  <TriangleAlertIcon aria-hidden="true" />
                  <AlertTitle>{tr("submit_failed", lang)}</AlertTitle>
                  <AlertDescription>{outcome.detail}</AlertDescription>
                </Alert>
              )}
              {outcome && outcome.ok && (
                <Alert>
                  <CircleCheckIcon className="text-pos" aria-hidden="true" />
                  <AlertTitle>{tr("submit_ok", lang)}</AlertTitle>
                  <AlertDescription>
                    <p>{outcome.detail}</p>
                    {(outcome.warnings?.length ?? 0) > 0 && (
                      <ul className="list-disc space-y-1 ps-5">
                        {outcome.warnings!.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    )}
                  </AlertDescription>
                </Alert>
              )}
              {!demo && (
                <p className="text-muted-foreground text-[0.8rem]">
                  {tr("submit_source_note", lang)}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <p className="text-muted-foreground mt-3 text-[0.8rem]">
          {tr("snapshot_note", lang)} · {snapshot.period}
        </p>
      </div>
    </section>
  );
}
