import { ArrowUpIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
} from "@/components/ui/item";
import { tr, type Lang } from "../lib/i18n";
import { useSnapshot } from "../lib/snapshot";
import { stampDate } from "../lib/format";
import type { ActivityEvent } from "../lib/types";
import { Stamp, SectionHead } from "./ui";

/**
 * The log, as a shadcn Item list. The tag is a Badge whose word carries the
 * meaning (the colour only agrees with it), and the time is a real `<time>`,
 * so the sequence survives being read aloud.
 */
const TAG_VARIANT: Record<ActivityEvent["tag"], string> = {
  EXCEL: "var(--neg)",
  AGENT: "var(--brass)",
  A2A: "var(--pos)",
  DATA: "var(--info)",
};

const TAG_LABEL: Record<ActivityEvent["tag"], string> = {
  EXCEL: "tag_excel",
  AGENT: "tag_agent",
  A2A: "tag_notice",
  DATA: "tag_data",
};

export function Activity({
  lang,
  events,
}: {
  lang: Lang;
  events: ActivityEvent[];
}) {
  const snapshot = useSnapshot();
  return (
    <section id="activity" className="border-border scroll-mt-6 border-t">
      <div className="shell py-14">
        <SectionHead
          id="activity-title"
          titleKey="log_title"
          subKey="log_sub"
          lang={lang}
        />
        <Card className="gap-0 py-0">
          <CardContent className="p-0">
            <ItemGroup className="gap-0 divide-y divide-border">
              {events.map((e, i) => (
                <Item
                  key={`${e.at}-${i}`}
                  role="listitem"
                  variant="default"
                  className="flex-wrap items-baseline gap-x-4 rounded-none border-0 px-5 py-3"
                >
                  <ItemMedia className="w-[3.4rem] justify-start font-mono text-[0.8rem] tabular-nums">
                    <time dateTime={e.at}>{e.at.slice(0, 5)}</time>
                  </ItemMedia>
                  <Badge
                    variant="outline"
                    className="shrink-0 text-[0.78rem] font-semibold tracking-wide uppercase"
                    style={{ color: TAG_VARIANT[e.tag] }}
                  >
                    {tr(TAG_LABEL[e.tag], lang)}
                  </Badge>
                  <ItemContent className="min-w-[16rem] flex-1">
                    <ItemDescription className="line-clamp-none text-[0.9rem] leading-relaxed text-foreground">
                      {e.text}
                    </ItemDescription>
                  </ItemContent>
                </Item>
              ))}
            </ItemGroup>
          </CardContent>
        </Card>
        <p className="text-muted-foreground mt-3 text-[0.8rem]">
          {tr("snapshot_note", lang)} · {stampDate(snapshot.generated_at, lang)}
        </p>
      </div>
    </section>
  );
}

const GLOSSARY: [string, string, "exact" | "ai" | "missing" | "portal_only"][] = [
  ["g_exact", "exact", "exact"],
  ["g_ai", "ai", "ai"],
  ["g_missing", "missing", "missing"],
  ["g_portal_only", "portal_only", "portal_only"],
];

export function Glossary({ lang }: { lang: Lang }) {
  return (
    <section id="glossary" className="border-border scroll-mt-6 border-t">
      <div className="shell py-14">
        <SectionHead id="glossary-title" titleKey="glossary_title" lang={lang} />
        <ItemGroup className="grid gap-4 md:grid-cols-2">
          {GLOSSARY.map(([key, , status]) => (
            <Item
              key={key}
              role="listitem"
              variant="outline"
              className="items-start gap-3 p-5"
            >
              <ItemMedia className="pt-0.5">
                <Stamp status={status} conf={82} lang={lang} />
              </ItemMedia>
              <ItemContent>
                <ItemDescription className="line-clamp-none text-[0.92rem] leading-relaxed">
                  {tr(key, lang)}
                </ItemDescription>
              </ItemContent>
            </Item>
          ))}
        </ItemGroup>
      </div>
    </section>
  );
}

export function Footer({ lang }: { lang: Lang }) {
  return (
    <footer className="border-border border-t">
      <div className="shell py-8">
        <p className="text-[0.9rem]">{tr("footer_legal", lang)}</p>
        <p className="prose-note text-muted-foreground mt-2 text-[0.85rem]">
          {tr("footer_fixtures", lang)}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-muted-foreground text-[0.8rem]">
            {tr("brand_tagline", lang)}
          </span>
          <Button asChild variant="link" size="sm" className="h-auto p-0 text-[0.8rem]">
            <a href="#main">
              <ArrowUpIcon aria-hidden="true" />
              {tr("back_to_top", lang)}
            </a>
          </Button>
        </div>
      </div>
    </footer>
  );
}
