import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { inr } from "@/lib/format";
import { tr, type Lang } from "@/lib/i18n";
import { useSnapshot } from "@/lib/snapshot";
import type { Status } from "@/lib/types";

/**
 * Credit per bill, coloured by what happened to it.
 *
 * This is the ledger's own data, drawn — not a decorative chart. The figures
 * are also in the table below, and the chart carries an accessible summary
 * because a canvas of bars says nothing to a screen reader.
 */

const SERIES: Record<Status, { key: string; color: string }> = {
  exact: { key: "status_matched", color: "var(--pos)" },
  ai: { key: "status_recovered", color: "var(--brass)" },
  missing: { key: "status_defaulting", color: "var(--neg)" },
  portal_only: { key: "status_late", color: "var(--info)" },
  unmatched: { key: "unresolved", color: "var(--muted-foreground)" },
};

export function ChartCredit({ lang }: { lang: Lang }) {
  const snapshot = useSnapshot();
  const rows = [...snapshot.matches].sort((a, b) => b.tax - a.tax);

  const config = Object.fromEntries(
    Object.entries(SERIES).map(([status, s]) => [
      status,
      { label: tr(s.key, lang), color: s.color },
    ]),
  ) as ChartConfig;

  const totals = rows.reduce<Record<string, number>>((acc, r) => {
    acc[r.status] = (acc[r.status] ?? 0) + r.tax;
    return acc;
  }, {});

  const summary = rows
    .map((r) => `${r.register_no} ${inr(r.tax)} ${tr(SERIES[r.status].key, lang)}`)
    .join("; ");

  return (
    <Card className="py-4">
      <CardHeader>
        <CardTitle className="text-base">{tr("chart_title", lang)}</CardTitle>
        <CardDescription>{tr("chart_sub", lang)}</CardDescription>
      </CardHeader>
      <CardContent>
        <figure className="m-0">
          <figcaption className="sr-only">
            {tr("chart_title", lang)}: {summary}
          </figcaption>
          <ChartContainer config={config} className="h-[16rem] w-full">
            <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="register_no"
                tickLine={false}
                axisLine={false}
                tickMargin={6}
                interval={0}
                angle={-40}
                height={54}
                textAnchor="end"
                fontSize={11}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                width={56}
                fontSize={11}
                tickFormatter={(value: number) => `₹${Math.round(value / 1000)}k`}
              />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    labelFormatter={(label) => String(label)}
                    formatter={(value) => inr(Number(value))}
                  />
                }
              />
              <Bar dataKey="tax" radius={4}>
                {rows.map((row) => (
                  <Cell key={row.register_no} fill={SERIES[row.status].color} />
                ))}
              </Bar>
            </BarChart>
          </ChartContainer>

          <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
            {(["exact", "ai", "missing", "portal_only"] as Status[]).map((status) => (
              <div key={status} className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="size-2.5 rounded-full"
                  style={{ background: SERIES[status].color }}
                />
                <dt className="text-muted-foreground text-[0.85rem]">
                  {tr(SERIES[status].key, lang)}
                </dt>
                <dd className="font-mono text-[0.85rem] tabular-nums">
                  {inr(totals[status] ?? 0)}
                </dd>
              </div>
            ))}
          </dl>
        </figure>
      </CardContent>
    </Card>
  );
}
