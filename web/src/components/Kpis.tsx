import { lazy, Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { alt, tr, type Lang } from "../lib/i18n";
import { SectionCards } from "./section-cards";

// The chart is the only thing on the page that needs a charting library, and
// most of the weight. Loading it on demand keeps the first paint small for a
// reader on a slow connection — and the figures are in the cards and the
// ledger either way.
const ChartCredit = lazy(() =>
  import("./chart-credit").then((m) => ({ default: m.ChartCredit })),
);

export function Kpis({ lang }: { lang: Lang }) {
  const english = alt("kpi_title", lang);

  return (
    <section id="numbers" className="shell scroll-mt-20 py-10 lg:py-12">
      <header className="mb-6 max-w-3xl">
        <h2 className="text-[1.5rem] font-semibold md:text-[1.85rem]">
          {tr("kpi_title", lang)}
        </h2>
        {english && (
          <p className="text-muted-foreground mt-1 text-[0.95rem]" lang="en">
            {english}
          </p>
        )}
      </header>

      <SectionCards lang={lang} />

      <p
        className="prose-note text-muted-foreground mt-5 border-s-2 ps-4 text-[0.95rem]"
        style={{ borderColor: "color-mix(in oklab, var(--brass) 60%, transparent)" }}
      >
        {tr("kpi_note", lang)}
      </p>

      <div className="mt-6">
        <Suspense fallback={<Skeleton className="h-[19rem] w-full rounded-2xl" />}>
          <ChartCredit lang={lang} />
        </Suspense>
      </div>
    </section>
  );
}
