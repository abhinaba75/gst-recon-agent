import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Item,
  ItemContent,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CheckIcon, FunctionSquareIcon } from "lucide-react";
import { inr } from "../lib/format";
import { alt, tr, type Lang } from "../lib/i18n";
import { rescuedOf, useSnapshot } from "../lib/snapshot";
import { Stamp } from "./ui";

const RULES = ["rule_gstin", "rule_tax", "rule_number"] as const;

/**
 * The demo's centrepiece, as two shadcn Tables side by side: the rows an Excel
 * VLOOKUP drops, and the same rows resolved with corroborated evidence. Both
 * tables reuse the ledger's column words, and each carries a caption, so a
 * reader that never sees the layout still knows what the numbers are.
 */
export function Comparison({ lang }: { lang: Lang }) {
  const snapshot = useSnapshot();
  const rescued = rescuedOf(snapshot);
  const { totals, excel_unmatched: failed } = snapshot;

  return (
    <section id="compare" className="border-border scroll-mt-6 border-t">
      <div className="shell py-14">
        <header className="mb-6 max-w-3xl">
          <h2 id="compare-title" className="text-[1.75rem] font-semibold md:text-[2rem]">
            {tr("compare_title", lang)}
          </h2>
          {alt("compare_title", lang) && (
            <p className="text-muted-foreground mt-1 text-[0.95rem]" lang="en">
              {alt("compare_title", lang)}
            </p>
          )}
        </header>

        <div className="grid gap-5 lg:grid-cols-2">
          {/* The failure, reconstructed exactly as a spreadsheet behaves. */}
          <Card role="article" aria-labelledby="compare-left">
            <CardHeader>
              <CardTitle id="compare-left" className="text-[1.12rem]">
                {tr("compare_left", lang)}
              </CardTitle>
              {alt("compare_left", lang) && (
                <CardDescription lang="en">{alt("compare_left", lang)}</CardDescription>
              )}
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Alert variant="destructive">
                <FunctionSquareIcon aria-hidden="true" />
                <AlertTitle>{tr("formula_label", lang)}</AlertTitle>
                <AlertDescription>
                  <code translate="no">=VLOOKUP(A2, &apos;GSTR-2B&apos;!A:F, 2, FALSE)</code>
                </AlertDescription>
              </Alert>

              <div className="flex flex-col gap-1">
                <span className="text-neg font-mono text-[1.5rem] tabular-nums">
                  {inr(totals.write_off)}
                </span>
                <span className="text-muted-foreground text-[0.85rem]">
                  {tr("written_off", lang)} — {failed.length} {tr("written_off_delta", lang)}
                </span>
              </div>

              <p className="text-muted-foreground text-[0.92rem] leading-relaxed">
                {tr("compare_left_body", lang)}
              </p>

              <Table>
                <TableCaption className="sr-only">{tr("compare_left", lang)}</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead>{tr("col_books", lang)}</TableHead>
                    <TableHead>{tr("col_supplier", lang)}</TableHead>
                    <TableHead className="text-end">{tr("col_itc", lang)}</TableHead>
                    <TableHead>{tr("col_status", lang)}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {failed.map((row) => (
                    <TableRow key={row.register_no}>
                      <TableCell className="whitespace-normal">
                        <code className="id text-[0.82rem]" translate="no">
                          {row.register_no}
                        </code>
                      </TableCell>
                      <TableCell className="text-muted-foreground min-w-[8rem] whitespace-normal text-[0.85rem]">
                        {row.supplier_name}
                      </TableCell>
                      <TableCell className="font-mono text-[0.85rem] tabular-nums">
                        {inr(row.tax)}
                      </TableCell>
                      <TableCell>
                        <Stamp status="unmatched" lang={lang} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* The same rows, resolved with corroborated evidence. */}
          <Card role="article" aria-labelledby="compare-right">
            <CardHeader>
              <CardTitle id="compare-right" className="text-[1.12rem]">
                {tr("compare_right", lang)}
              </CardTitle>
              {alt("compare_right", lang) && (
                <CardDescription lang="en">{alt("compare_right", lang)}</CardDescription>
              )}
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <ItemGroup className="gap-1">
                {RULES.map((key) => (
                  <Item key={key} role="listitem" size="xs" variant="muted">
                    <ItemMedia variant="icon">
                      <CheckIcon className="text-pos" aria-hidden="true" />
                    </ItemMedia>
                    <ItemContent>
                      <ItemTitle className="text-[0.85rem]">{tr(key, lang)}</ItemTitle>
                    </ItemContent>
                  </Item>
                ))}
              </ItemGroup>

              <div className="flex flex-col gap-1">
                <span className="text-pos font-mono text-[1.5rem] tabular-nums">
                  {inr(totals.rescued)}
                </span>
                <span className="text-muted-foreground text-[0.85rem]">
                  {tr("rescued_metric", lang)} — {rescued.length} {tr("rescued_delta", lang)}
                </span>
              </div>

              <p className="text-muted-foreground text-[0.92rem] leading-relaxed">
                {tr("compare_right_body", lang)}
              </p>

              <Table>
                <TableCaption className="sr-only">{tr("compare_right", lang)}</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead>{tr("col_books", lang)}</TableHead>
                    <TableHead>{tr("col_portal", lang)}</TableHead>
                    <TableHead className="text-end">{tr("col_itc", lang)}</TableHead>
                    <TableHead>{tr("col_status", lang)}</TableHead>
                    <TableHead>{tr("col_evidence", lang)}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rescued.map((row) => (
                    <TableRow key={row.register_no}>
                      <TableCell className="whitespace-normal">
                        <code className="id text-[0.82rem]" translate="no">
                          {row.register_no} → {row.portal_no}
                        </code>
                      </TableCell>
                      <TableCell className="text-muted-foreground min-w-[8rem] whitespace-normal text-[0.85rem]">
                        {row.supplier_name}
                      </TableCell>
                      <TableCell className="text-pos font-mono text-[0.85rem] tabular-nums">
                        {inr(row.tax)}
                      </TableCell>
                      <TableCell>
                        <Stamp status="ai" conf={row.ai_conf} lang={lang} />
                      </TableCell>
                      <TableCell className="text-muted-foreground max-w-[20rem] min-w-[12rem] text-[0.82rem] leading-relaxed whitespace-normal">
                        {row.reason}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
