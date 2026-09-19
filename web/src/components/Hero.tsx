import { ArrowRightIcon, ReceiptIndianRupeeIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { inr, inrShort, pct } from "../lib/format";
import { alt, tr, type Lang } from "../lib/i18n";
import { useSnapshot } from "../lib/snapshot";

/**
 * The first screen. Everything here is a shadcn component — Badge for the
 * eyebrow, Button for the two calls to action, Card for the figures, and a
 * Progress bar for the share of the claim that was rescued. The bar is
 * labelled, and the same numbers are written out beside it, so nothing is
 * carried by the width of a coloured line.
 */
export function Hero({ lang }: { lang: Lang }) {
  const snapshot = useSnapshot();
  const { totals, counts } = snapshot;
  const rescuedShare = totals.total ? Math.round((totals.rescued / totals.total) * 100) : 0;
  const english = alt("hero_title", lang);

  return (
    <section id="top" className="border-border relative scroll-mt-16 overflow-hidden border-b">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 -top-24 h-72 opacity-70"
        style={{
          background:
            "radial-gradient(48% 100% at 12% 0%, color-mix(in oklab, var(--brass) 16%, transparent), transparent 72%), radial-gradient(46% 100% at 82% 6%, color-mix(in oklab, var(--pos) 12%, transparent), transparent 72%)",
        }}
      />
      <div className="shell relative py-10 md:py-16">
        <Badge
          variant="outline"
          className="text-muted-foreground h-7 gap-1.5 px-3 text-[0.78rem] font-normal"
        >
          <ReceiptIndianRupeeIcon aria-hidden="true" />
          {tr("hero_eyebrow", lang)}
        </Badge>

        <h1 className="mt-5 max-w-3xl text-[1.9rem] leading-[1.12] font-semibold md:text-[3rem]">
          {tr("hero_title", lang)}
        </h1>
        {english && (
          <p className="text-muted-foreground mt-2 text-[1.05rem]" lang="en">
            {english}
          </p>
        )}

        <p className="prose-note text-muted-foreground mt-6 text-[1.02rem]">{tr("hero_sub", lang)}</p>
        <p className="prose-note text-muted-foreground mt-3 text-[0.95rem]">{tr("hero_body", lang)}</p>

        <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
          <Button asChild size="lg" className="min-h-11 w-full focus-visible:ring-3 sm:w-auto">
            <a href="#get-started">
              {tr("cta_start", lang)}
              <ArrowRightIcon data-icon="inline-end" aria-hidden="true" />
            </a>
          </Button>
          <Button
            asChild
            variant="outline"
            size="lg"
            className="min-h-11 w-full sm:w-auto"
          >
            <a href="#numbers">{tr("cta_numbers", lang)}</a>
          </Button>
          <span className="text-muted-foreground text-[0.85rem] sm:ms-1">
            {tr("cta_start_hint", lang)}
          </span>
        </div>

        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Card className="gap-3 py-4">
            <CardHeader>
              <CardDescription>{tr("kpi_exact", lang)}</CardDescription>
              <CardTitle className="font-mono text-2xl font-semibold tabular-nums">
                {inr(totals.exact)}
              </CardTitle>
              <CardAction>
                <Badge variant="outline">{inrShort(totals.exact, lang)}</Badge>
              </CardAction>
            </CardHeader>
          </Card>

          <Card className="gap-3 py-4">
            <CardHeader>
              <CardDescription>{tr("kpi_rescued", lang)}</CardDescription>
              <CardTitle className="text-brass font-mono text-2xl font-semibold tabular-nums">
                {inr(totals.rescued)}
              </CardTitle>
              <CardAction>
                <Badge variant="outline">{pct(totals.rescued / (totals.total || 1))}</Badge>
              </CardAction>
            </CardHeader>
          </Card>

          <Card className="gap-3 py-4 sm:col-span-2 xl:col-span-1">
            <CardHeader>
              <CardDescription>{tr("kpi_risk", lang)}</CardDescription>
              <CardTitle className="text-neg font-mono text-2xl font-semibold tabular-nums">
                {inr(totals.risk)}
              </CardTitle>
              <CardAction>
                <Badge variant="outline">
                  {tr("kpi_rule88d", lang)} · {snapshot.period}
                </Badge>
              </CardAction>
            </CardHeader>
          </Card>
        </div>

        {/* The share of the claim that came back, as a labelled bar. */}
        <Card className="mt-4 gap-3 py-4">
          <CardContent className="flex flex-col gap-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-[0.9rem] font-medium">{tr("kpi_rescued", lang)}</span>
              <span className="text-muted-foreground font-mono text-[0.85rem] tabular-nums">
                {inr(totals.rescued)} / {inr(totals.total)}
              </span>
            </div>
            <Progress
              value={rescuedShare}
              aria-label={tr("kpi_rescued", lang)}
              aria-valuetext={`${rescuedShare}%`}
              className="h-2"
            />
            <p className="text-muted-foreground text-[0.82rem]">
              {counts.rescued} {tr("rescued_delta", lang)} · {totals.total ? `${rescuedShare}%` : "—"}
            </p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
