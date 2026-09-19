import { useId, type ReactNode } from "react";
import { InfoIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { alt, tr, type Lang } from "../lib/i18n";
import type { Status } from "../lib/types";

export {
  Card,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
};

/**
 * A hover card carrying the explanation of whatever it sits next to.
 *
 * The trigger is a real button, so the card opens on focus as well as on
 * hover, and the content is wired to the trigger with `aria-describedby` —
 * a reader that never hovers still gets the sentence. The panel is a
 * convenience on top of text that is already on the page, never the only
 * place a fact lives.
 */
export function HoverInfo({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <HoverCard openDelay={140} closeDelay={90}>
      <HoverCardTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className={`text-muted-foreground shrink-0 rounded-full ${className}`}
          aria-label={label}
          aria-describedby={id}
        >
          <InfoIcon aria-hidden="true" />
        </Button>
      </HoverCardTrigger>
      <HoverCardContent id={id} className="w-[17rem] text-[0.82rem] leading-relaxed">
        {children}
      </HoverCardContent>
    </HoverCard>
  );
}

/** Section heading: active language, with the English line beneath it. */
export function SectionHead({
  id,
  titleKey,
  subKey,
  lang,
}: {
  id: string;
  titleKey: string;
  subKey?: string;
  lang: Lang;
}) {
  const english = alt(titleKey, lang);
  return (
    <header className="mb-6 max-w-3xl">
      <h2 id={id} className="text-[1.75rem] font-semibold md:text-[2rem]">
        {tr(titleKey, lang)}
      </h2>
      {english && (
        <p className="text-muted-foreground mt-1 text-[0.95rem]" lang="en">
          {english}
        </p>
      )}
      {subKey && (
        <p className="prose-note text-muted-foreground mt-3 text-[0.98rem]">
          {tr(subKey, lang)}
        </p>
      )}
    </header>
  );
}

const STAMP_TEXT: Record<Status, { key: string; conf?: boolean }> = {
  exact: { key: "status_matched" },
  ai: { key: "status_recovered", conf: true },
  missing: { key: "status_defaulting" },
  portal_only: { key: "status_late" },
  unmatched: { key: "unresolved" },
};

const STAMP_COLOR: Record<Status, string> = {
  exact: "var(--pos)",
  ai: "var(--brass)",
  missing: "var(--neg)",
  portal_only: "var(--info)",
  unmatched: "var(--neg)",
};

/**
 * Status stamp — a shadcn Badge wearing this product's colours. The colour is
 * decoration; the words are the information, so the label is translated and
 * the percentage is written out, never implied by a hue.
 */
export function Stamp({
  status,
  conf = 0,
  lang = "en",
}: {
  status: Status;
  conf?: number;
  lang?: Lang;
}) {
  const { key, conf: withConf } = STAMP_TEXT[status];
  return (
    <Badge
      variant="outline"
      className="stamp"
      style={{
        color: STAMP_COLOR[status],
        borderColor: "currentColor",
        background: "color-mix(in oklab, currentColor 11%, transparent)",
      }}
    >
      {tr(key, lang)}
      {withConf && conf ? ` · ${conf}%` : ""}
    </Badge>
  );
}
