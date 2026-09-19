import type { ReactNode } from "react";
import { AlertTriangleIcon, ReceiptIndianRupeeIcon, ShieldCheckIcon, TrendingUpIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { inr, inrShort, pct } from "@/lib/format";
import { tr, type Lang } from "@/lib/i18n";
import { useSnapshot } from "@/lib/snapshot";

/**
 * The four figures, as section cards. Every badge is a fact from the
 * reconciliation — a bill count, a share of the total, a legal reference —
 * rather than a decorative " +12.5%" this build cannot support.
 */
function StatCard({
  label,
  value,
  badge,
  footer,
  note,
}: {
  label: string;
  value: string;
  badge: ReactNode;
  footer: string;
  note: string;
}) {
  return (
    <Card className="@container/card gap-3 py-4">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="font-mono text-2xl font-semibold tabular-nums @[250px]/card:text-[1.7rem]">
          {value}
        </CardTitle>
        <CardAction>{badge}</CardAction>
      </CardHeader>
      <CardFooter className="flex-col items-start gap-1 text-sm">
        <div className="flex items-center gap-2 font-medium">
          {footer}
          {note}
        </div>
      </CardFooter>
    </Card>
  );
}

export function SectionCards({ lang }: { lang: Lang }) {
  const snapshot = useSnapshot();
  const { totals, counts } = snapshot;
  const share = totals.total ? pct(totals.rescued / totals.total) : "0%";

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        label={tr("kpi_total", lang)}
        value={inr(totals.total)}
        badge={
          <Badge variant="outline">
            <ReceiptIndianRupeeIcon />
            {counts.books}
          </Badge>
        }
        footer={tr("kpi_bills", lang)}
        note={inrShort(totals.total, lang)}
      />
      <StatCard
        label={tr("kpi_exact", lang)}
        value={inr(totals.exact)}
        badge={
          <Badge variant="outline">
            <ShieldCheckIcon />
            {tr("kpi_zero_risk", lang)}
          </Badge>
        }
        footer={tr("kpi_bills", lang)}
        note={inrShort(totals.exact, lang)}
      />
      <StatCard
        label={tr("kpi_rescued", lang)}
        value={inr(totals.rescued)}
        badge={
          <Badge variant="outline">
            <TrendingUpIcon />
            {`${share} ${tr("kpi_of_total", lang)}`}
          </Badge>
        }
        footer={tr("rescued_delta", lang)}
        note={String(counts.rescued)}
      />
      <StatCard
        label={tr("kpi_risk", lang)}
        value={inr(totals.risk)}
        badge={
          <Badge variant="outline">
            <AlertTriangleIcon />
            {tr("kpi_rule88d", lang)}
          </Badge>
        }
        footer={tr("status_defaulting", lang)}
        note={String(counts.missing)}
      />
    </div>
  );
}
