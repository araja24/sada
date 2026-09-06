"use client";

import * as React from "react";
import { motion, AnimatePresence, type Variants } from "framer-motion";
import { X, Mail, Lock, ArrowRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/* Provider marks. Lucide ships no brand logos, so these are inline SVGs.
   Sada currently authenticates with email and password only (ADR-0002), so
   `providers` is opt-in: pass none and the grid is not rendered at all,
   rather than showing buttons that do nothing. */

const GoogleIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
    <path
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      fill="#4285F4"
    />
    <path
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      fill="#34A853"
    />
    <path
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      fill="#FBBC05"
    />
    <path
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      fill="#EA4335"
    />
  </svg>
);

const AppleIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <path d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701" />
  </svg>
);

const MicrosoftIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 88 88" className={className} aria-hidden="true">
    <path fill="#f35325" d="M0 0h42v42H0z" />
    <path fill="#81bc06" d="M46 0h42v42H46z" />
    <path fill="#05a6f0" d="M0 46h42v42H0z" />
    <path fill="#ffba08" d="M46 46h42v42H46z" />
  </svg>
);

const GitHubIcon = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
  </svg>
);

const PROVIDER_ICONS: Record<string, (p: { className?: string }) => React.JSX.Element> = {
  Google: GoogleIcon,
  Apple: AppleIcon,
  Microsoft: MicrosoftIcon,
  Github: GitHubIcon,
};

export type AuthMode = "signup" | "login";

export interface AuthModalProps {
  /** Whether the dialog is showing. Controlled by the parent. */
  open: boolean;
  /** Called with false when the user dismisses the dialog. */
  onOpenChange: (open: boolean) => void;
  /** Which face the dialog opens on. */
  mode: AuthMode;
  /** Called when the user flips between sign up and sign in. */
  onModeChange: (mode: AuthMode) => void;
  /**
   * Submit handler. Resolve to close the dialog; reject with an Error whose
   * message is shown inline. The parent owns the actual API call.
   */
  onSubmit: (mode: AuthMode, email: string, password: string) => Promise<void>;
  /**
   * Optional social providers to offer. Omit it and no provider grid is
   * rendered, which is the honest default until an OAuth backend exists.
   */
  providers?: string[];
  /** Called when a provider button is pressed. */
  onProviderLogin?: (provider: string) => void;
  className?: string;
}

const container: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  show: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.3, ease: "easeInOut", staggerChildren: 0.05 },
  },
  exit: {
    opacity: 0,
    scale: 0.95,
    transition: { duration: 0.2, ease: "easeInOut" },
  },
};

const item: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

function AuthModal({
  open,
  onOpenChange,
  mode,
  onModeChange,
  onSubmit,
  providers,
  onProviderLogin,
  className,
}: AuthModalProps) {
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const isSignup = mode === "signup";

  // Clear the form whenever the dialog is dismissed, so a reopen is fresh.
  React.useEffect(() => {
    if (!open) {
      setPassword("");
      setError(null);
      setBusy(false);
    }
  }, [open]);

  // Escape closes, matching what people expect from a modal.
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await onSubmit(mode, email.trim(), password);
      setEmail("");
      setPassword("");
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="auth-modal-title"
        >
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => onOpenChange(false)}
            className="absolute inset-0 bg-[#2b2723]/25 backdrop-blur-sm"
          />

          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            exit="exit"
            className={cn(
              "relative w-full max-w-[380px] overflow-hidden rounded-3xl bg-background p-6 shadow-2xl border border-border ring-1 ring-foreground/5",
              className,
            )}
          >
            <div className="absolute right-4 top-4">
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                aria-label="Close"
                className="rounded-full p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <motion.div variants={item} className="mb-7 text-center">
              <h2
                id="auth-modal-title"
                className="text-2xl font-semibold tracking-tight text-foreground"
              >
                {isSignup ? "Save your attempts" : "Welcome back"}
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {isSignup
                  ? "Create an account to keep your recitation history across devices."
                  : "Sign in to pick up where you left off."}
              </p>
            </motion.div>

            {providers && providers.length > 0 && (
              <>
                <motion.div
                  variants={item}
                  className="grid grid-cols-4 gap-3 mb-6"
                >
                  {providers.map((name) => {
                    const Icon = PROVIDER_ICONS[name];
                    if (!Icon) return null;
                    return (
                      <button
                        key={name}
                        type="button"
                        onClick={() => onProviderLogin?.(name)}
                        aria-label={`Continue with ${name}`}
                        className="flex aspect-square items-center justify-center rounded-2xl border border-border bg-background transition-all hover:bg-muted hover:scale-105 active:scale-95"
                      >
                        <Icon className="h-5 w-5" />
                      </button>
                    );
                  })}
                </motion.div>

                <motion.div variants={item} className="relative mb-6">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t border-border" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-background px-2 text-muted-foreground">
                      Or continue with email
                    </span>
                  </div>
                </motion.div>
              </>
            )}

            <motion.form variants={item} onSubmit={handleSubmit} noValidate>
              <div className="relative mb-3">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                  required
                  className="h-11 w-full rounded-full border border-border bg-muted pl-10 pr-4 text-sm text-foreground outline-none transition-all placeholder:text-muted-foreground focus:border-primary focus:bg-background focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  autoComplete={isSignup ? "new-password" : "current-password"}
                  minLength={8}
                  required
                  className="h-11 w-full rounded-full border border-border bg-muted pl-10 pr-12 text-sm text-foreground outline-none transition-all placeholder:text-muted-foreground focus:border-primary focus:bg-background focus:ring-1 focus:ring-primary"
                />
                <button
                  type="submit"
                  disabled={busy}
                  aria-label={isSignup ? "Sign up" : "Log in"}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full h-8 w-8 flex items-center justify-center bg-primary text-primary-foreground transition-transform hover:scale-95 active:scale-90 disabled:opacity-50 disabled:hover:scale-100"
                >
                  {busy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowRight className="h-4 w-4" />
                  )}
                </button>
              </div>

              {error && (
                <p role="alert" className="mt-3 text-sm text-destructive">
                  {error}
                </p>
              )}

              <button
                type="button"
                onClick={() => onModeChange(isSignup ? "login" : "signup")}
                className="mt-4 w-full text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                {isSignup
                  ? "I already have an account"
                  : "I need to create an account"}
              </button>
            </motion.form>

            <motion.div variants={item} className="mt-6 text-center">
              <p className="text-xs text-muted-foreground">
                You can practice without an account. We'll only keep the
                recitations you record on this device. If you sign up, your
                history can follow you to other devices. We never share any of
                it.
              </p>
            </motion.div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

export { AuthModal };
export default AuthModal;
