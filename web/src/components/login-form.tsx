import { useState } from "react";
import { cn } from "cn";
import { LogInIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { tr, type Lang } from "@/lib/i18n";

export interface LoginFormProps extends React.ComponentProps<"div"> {
  lang: Lang;
  busy: boolean;
  error: string | null;
  demoHint: string | null;
  /** Named `onSignIn`, not `onSubmit`, which the div's own props already own. */
  onSignIn: (email: string, password: string) => void;
}

/**
 * Adapted from the login-04 block. The Apple/Google/Meta buttons and the
 * "forgot your password" link are gone: this build has no OAuth providers and
 * nothing to reset, and buttons that do nothing are worse than no buttons.
 */
export function LoginForm({
  className,
  lang,
  busy,
  error,
  demoHint,
  onSignIn,
  ...props
}: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card className="overflow-hidden p-0">
        <CardContent className="grid p-0 md:grid-cols-2">
          <form
            className="p-6 md:p-8"
            onSubmit={(e) => {
              e.preventDefault();
              onSignIn(email, password);
            }}
          >
            <FieldGroup>
              <div className="flex flex-col items-center gap-2 text-center">
                <h1 className="font-display text-2xl font-semibold">
                  {tr("login_title", lang)}
                </h1>
                <p className="text-muted-foreground text-balance text-sm">
                  {tr("login_sub", lang)}
                </p>
              </div>

              <Field>
                <FieldLabel htmlFor="login-email">{tr("login_email", lang)}</FieldLabel>
                <Input
                  id="login-email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  spellCheck={false}
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="login-password">
                  {tr("login_password", lang)}
                </FieldLabel>
                <Input
                  id="login-password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>

              {error && (
                <FieldError role="alert" aria-live="polite">
                  {error}
                </FieldError>
              )}

              <Field>
                <Button type="submit" disabled={busy}>
                  {busy ? <Spinner className="text-current" /> : <LogInIcon />}
                  {busy ? tr("login_checking", lang) : tr("login_submit", lang)}
                </Button>
              </Field>

              {demoHint && (
                <FieldDescription className="text-center">{demoHint}</FieldDescription>
              )}
            </FieldGroup>
          </form>

          {/* The reference block puts a stock photo here. These four figures
              are the product's own, and they double as the pitch. */}
          <div className="bg-muted relative hidden flex-col justify-center gap-3 p-8 md:flex">
            <p className="text-sm font-medium">{tr("login_benefits", lang)}</p>
            <p className="prose-note text-muted-foreground text-sm leading-relaxed">
              {tr("login_note", lang)}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
