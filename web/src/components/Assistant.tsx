import { useEffect, useId, useRef, useState } from "react";
import { ArrowUpIcon, BotIcon, RotateCcwIcon, XIcon } from "lucide-react";

import { askAssistant } from "../lib/assistant";
import { tr, type Lang } from "../lib/i18n";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { InputGroup, InputGroupTextarea } from "@/components/ui/input-group";
import { Kbd } from "@/components/ui/kbd";
import {
  Questionnaire,
  QuestionnaireChoice,
  QuestionnaireChoices,
  QuestionnaireItem,
  QuestionnaireTitle,
} from "@/components/ui/questionnaire";
import {
  MessageScroller,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller";
import { BorderBeam } from "@/components/ui/border-beam";
import { Spinner } from "@/components/ui/spinner";

interface Message {
  id: number;
  role: "user" | "assistant";
  text: string;
  source?: "model" | "guide" | "none";
}

const SUGGESTIONS = ["asst_q1", "asst_q2", "asst_q3", "asst_q4"] as const;

/**
 * The question box.
 *
 * Shape is the requested one — a beam-lit card, a row of chips, a round
 * arrow-up to send — with every chip carrying something true rather than a
 * mode picker this product does not have: the left chip states where the
 * last answer came from (the model, or the built-in guide), and the second
 * is the key that sends. Before the first answer the row is just the hint
 * and the button, because there is nothing yet to claim.
 *
 * Extracted and exported so a headless render can hold it to that.
 */
export function AssistantComposer({
  lang,
  theme = "light",
  draft,
  busy,
  source,
  inputRef,
  inputId,
  onDraft,
  onSend,
}: {
  lang: Lang;
  theme?: "light" | "dark";
  draft: string;
  busy: boolean;
  /** Which engine produced the last answer, if one has been produced. */
  source: "model" | "guide" | null;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  inputId: string;
  onDraft: (value: string) => void;
  onSend: () => void;
}) {
  return (
    <BorderBeam size="md" colorVariant="colorful" theme={theme} className="rounded-[20px]">
      {/* No static border of its own: inside the beam that would read as two
          edges. The surface stays opaque so the beam has something to sit on,
          and the group's focus ring is kept — a keyboard user needs to see
          where the caret went. */}
      <InputGroup className="h-auto w-full flex-col items-stretch gap-2 rounded-[20px] border-0 bg-card p-2 shadow-none dark:bg-card">
        <InputGroupTextarea
          id={inputId}
          ref={inputRef}
          rows={2}
          value={draft}
          onChange={(e) => onDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          placeholder={tr("asst_placeholder", lang)}
          className="min-h-12 border-0 bg-transparent text-[0.92rem] shadow-none focus-visible:ring-0"
        />
        <div className="flex items-center gap-2">
          {source && (
            <Badge
              variant="secondary"
              className="h-6 rounded-full px-2 text-[0.72rem] font-normal"
            >
              {source === "model"
                ? tr("asst_source_model", lang)
                : tr("asst_source_guide", lang)}
            </Badge>
          )}
          <Kbd className="hidden sm:inline-flex">Enter</Kbd>
          <Button
            type="submit"
            size="icon-sm"
            className="ms-auto rounded-full"
            disabled={busy || draft.trim().length === 0}
            aria-label={tr("asst_send", lang)}
            title={tr("asst_send", lang)}
          >
            {busy ? <Spinner className="text-current" /> : <ArrowUpIcon aria-hidden="true" />}
          </Button>
        </div>
      </InputGroup>
    </BorderBeam>
  );
}

/**
 * One question, four answers, as a shadcn questionnaire: a real radio group
 * with a legend, so arrow keys and the browser's own radio behaviour carry it,
 * and the labels are the questions themselves.
 */
export function AssistantSuggestions({
  lang,
  onPick,
}: {
  lang: Lang;
  onPick: (key: string) => void;
}) {
  return (
    <Questionnaire className="mt-5" onSubmit={(e) => e.preventDefault()}>
      <QuestionnaireItem name="asst-question">
        <QuestionnaireTitle>{tr("asst_suggest", lang)}</QuestionnaireTitle>
        <QuestionnaireChoices>
          {SUGGESTIONS.map((key) => (
            <QuestionnaireChoice key={key} value={key} onChange={() => onPick(key)}>
              {tr(key, lang)}
            </QuestionnaireChoice>
          ))}
        </QuestionnaireChoices>
      </QuestionnaireItem>
    </Questionnaire>
  );
}

/**
 * The in-page helper. The thread is a shadcn MessageScroller, which owns the
 * scroll position and the "jump to latest" button; the composer is an
 * InputGroup around a Textarea. Every answer says where it came from, so a
 * scripted answer is never dressed up as a model's.
 */
export function Assistant({
  lang,
  theme = "light",
}: {
  lang: Lang;
  /** The beam follows the page's own theme, not the OS preference. */
  theme?: "light" | "dark";
}) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [usedModel, setUsedModel] = useState(false);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const panelId = useId();
  const nextId = useRef(1);

  // Opening the panel moves focus to the question box: the launcher is a
  // button, so a keyboard user is otherwise left at the bottom of the page.
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  async function send(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setDraft("");
    setMessages((prev) => [...prev, { id: nextId.current++, role: "user", text }]);
    setBusy(true);
    const reply = await askAssistant(text, lang);
    if (reply.source === "model") setUsedModel(true);
    setMessages((prev) => [
      ...prev,
      {
        id: nextId.current++,
        role: "assistant",
        text: reply.ok ? reply.answer : tr("asst_no_answer", lang),
        source: reply.source,
      },
    ]);
    setBusy(false);
  }

  if (!open) {
    return (
      <Button
        type="button"
        size="lg"
        className="fixed end-5 bottom-5 z-[61] min-h-12 gap-2 rounded-full px-5 shadow-lg"
        onClick={() => setOpen(true)}
        aria-expanded={false}
      >
        <BotIcon aria-hidden="true" />
        {tr("asst_launch", lang)}
      </Button>
    );
  }

  return (
    <section
      id={panelId}
      className="assistant-panel"
      aria-label={tr("asst_title", lang)}
    >
      <MessageScrollerProvider defaultScrollPosition="end">
        <header className="border-border flex items-start gap-2 border-b p-4">
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-[1.05rem] font-semibold">
              {tr("asst_title", lang)}
            </h2>
            <p className="text-muted-foreground mt-0.5 text-[0.82rem]">
              {tr("asst_sub", lang)}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="shrink-0"
            onClick={() => setMessages([])}
            disabled={messages.length === 0}
            aria-label={tr("asst_clear", lang)}
            title={tr("asst_clear", lang)}
          >
            <RotateCcwIcon aria-hidden="true" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="shrink-0"
            onClick={() => setOpen(false)}
            aria-label={tr("asst_close", lang)}
            title={tr("asst_close", lang)}
          >
            <XIcon aria-hidden="true" />
          </Button>
        </header>

        <MessageScroller className="flex-1">
          <MessageScrollerViewport
            role="log"
            aria-live="polite"
            aria-label={tr("asst_title", lang)}
            className="px-4 py-3"
          >
            <MessageScrollerContent className="gap-3">
              {messages.length === 0 && (
                <MessageScrollerItem>
                  <Empty className="border-0 p-0">
                    <EmptyHeader>
                      <EmptyMedia variant="icon">
                        <BotIcon aria-hidden="true" />
                      </EmptyMedia>
                      <EmptyTitle>{tr("asst_title", lang)}</EmptyTitle>
                      <EmptyDescription>{tr("asst_empty", lang)}</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                  <AssistantSuggestions lang={lang} onPick={(key) => void send(tr(key, lang))} />
                </MessageScrollerItem>
              )}

              {messages.map((m) => (
                <MessageScrollerItem
                  key={m.id}
                  messageId={String(m.id)}
                  className={`bubble ${m.role === "user" ? "bubble-user" : "bubble-bot"}`}
                >
                  {m.role === "user" ? (
                    <span className="sr-only">{tr("asst_send", lang)}: </span>
                  ) : null}
                  {m.text}
                  {m.source && (
                    <Badge
                      variant="secondary"
                      className="mt-2 flex w-fit text-[0.72rem] font-normal"
                    >
                      {m.source === "model"
                        ? tr("asst_source_model", lang)
                        : tr("asst_source_guide", lang)}
                    </Badge>
                  )}
                </MessageScrollerItem>
              ))}

              {busy && (
                <MessageScrollerItem
                  scrollAnchor
                  className="text-muted-foreground flex items-center gap-2 text-[0.85rem]"
                >
                  <Spinner />
                  {tr("asst_thinking", lang)}
                </MessageScrollerItem>
              )}
            </MessageScrollerContent>
          </MessageScrollerViewport>
        </MessageScroller>

        <form
          className="border-border border-t p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send(draft);
          }}
        >
          <label htmlFor={`${panelId}-input`} className="sr-only">
            {tr("asst_placeholder", lang)}
          </label>
          <AssistantComposer
            lang={lang}
            theme={theme}
            draft={draft}
            busy={busy}
            source={
              messages.some((m) => m.source)
                ? usedModel
                  ? "model"
                  : "guide"
                : null
            }
            inputRef={inputRef}
            inputId={`${panelId}-input`}
            onDraft={setDraft}
            onSend={() => void send(draft)}
          />
          <p className="text-muted-foreground mt-2 text-[0.75rem] leading-relaxed">
            {usedModel ? tr("asst_disclaimer", lang) : tr("asst_offline", lang)}
          </p>
        </form>
      </MessageScrollerProvider>
    </section>
  );
}
