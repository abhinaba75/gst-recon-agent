import { ArrowRightIcon, BadgeCheckIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
} from "@/components/ui/item";
import { alt, tr, type Lang } from "../lib/i18n";

const STEPS = [
  ["gs_step1_t", "gs_step1_d"],
  ["gs_step2_t", "gs_step2_d"],
  ["gs_step3_t", "gs_step3_d"],
  ["gs_step4_t", "gs_step4_d"],
] as const;

const PREREQS = ["gs_prereq_1", "gs_prereq_2", "gs_prereq_3"] as const;

/**
 * "Get started" as a shadcn Item list: an outline Item per prerequisite, a
 * numbered Card per step, then the two supporting facts. The steps are a real
 * ordered list — `<ol>`/`<li>` around a Card — so a screen reader counts them.
 */
export function GetStarted({ lang }: { lang: Lang }) {
  return (
    <section id="get-started" className="border-border scroll-mt-20 border-b">
      <div className="shell py-12 md:py-14">
        <header className="mb-6 max-w-3xl">
          <h2 className="text-[1.75rem] font-semibold md:text-[2rem]">
            {tr("gs_title", lang)}
          </h2>
          {alt("gs_title", lang) && (
            <p className="text-muted-foreground mt-1 text-[0.95rem]" lang="en">
              {alt("gs_title", lang)}
            </p>
          )}
          <p className="prose-note text-muted-foreground mt-3 text-[0.98rem]">
            {tr("gs_sub", lang)}
          </p>
        </header>

        <Card className="mb-5 gap-3 py-5">
          <CardHeader>
            <CardTitle className="text-[1.05rem]">{tr("gs_prereq_title", lang)}</CardTitle>
          </CardHeader>
          <CardContent>
            <ItemGroup className="gap-2">
              {PREREQS.map((key) => (
                <Item
                  key={key}
                  role="listitem"
                  variant="muted"
                  size="sm"
                  className="items-start"
                >
                  <ItemMedia variant="icon">
                    <BadgeCheckIcon className="text-primary" aria-hidden="true" />
                  </ItemMedia>
                  <ItemContent>
                    <ItemDescription className="text-[0.94rem] leading-relaxed text-foreground">
                      {tr(key, lang)}
                    </ItemDescription>
                  </ItemContent>
                </Item>
              ))}
            </ItemGroup>
          </CardContent>
        </Card>

        <ol className="grid gap-4 md:grid-cols-2">
          {STEPS.map(([titleKey, bodyKey], i) => (
            <li key={titleKey}>
              <Card className="h-full gap-3 py-5">
                <CardHeader>
                  <CardTitle className="flex items-center gap-3 text-[1.05rem]">
                    <Badge
                      variant="outline"
                      className="font-display size-7 shrink-0 justify-center rounded-full text-[0.9rem]"
                      aria-hidden="true"
                    >
                      {i + 1}
                    </Badge>
                    {tr(titleKey, lang)}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="prose-note text-muted-foreground text-[0.94rem]">
                    {tr(bodyKey, lang)}
                  </p>
                </CardContent>
              </Card>
            </li>
          ))}
        </ol>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Card className="gap-3 py-5">
            <CardHeader>
              <CardTitle className="text-[1.05rem]">{tr("gs_data_title", lang)}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="prose-note text-muted-foreground text-[0.94rem]">
                {tr("gs_data_d", lang)}
              </p>
            </CardContent>
          </Card>
          <Card className="gap-3 py-5">
            <CardHeader>
              <CardTitle className="text-[1.05rem]">{tr("gs_help_title", lang)}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="prose-note text-muted-foreground text-[0.94rem]">
                {tr("gs_help_d", lang)}
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
          <Button asChild size="lg" className="min-h-11 w-full sm:w-auto">
            <a href="#submit">
              {tr("nav_submit", lang)}
              <ArrowRightIcon data-icon="inline-end" aria-hidden="true" />
            </a>
          </Button>
          <Button asChild variant="outline" size="lg" className="min-h-11 w-full sm:w-auto">
            <a href="#recovery">{tr("nav_recovery", lang)}</a>
          </Button>
          <p className="text-muted-foreground text-[0.85rem]">
            {tr("gs_demo_note", lang)}{" "}
            <span lang="en" className="text-muted-foreground">
              {alt("gs_need_console", lang)}
            </span>
          </p>
        </div>
      </div>
    </section>
  );
}
