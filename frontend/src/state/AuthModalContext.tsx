"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import { AuthModal, type AuthMode } from "@/components/ui/auth-modal";
import { useSession } from "./SessionContext";

interface AuthModalValue {
  /** Open the auth dialog on the given face. */
  openAuth: (mode: AuthMode) => void;
  closeAuth: () => void;
  isOpen: boolean;
}

const AuthModalContext = createContext<AuthModalValue | null>(null);

export function AuthModalProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const [mode, setMode] = useState<AuthMode>("signup");
  const { refresh } = useSession();

  const openAuth = useCallback((next: AuthMode) => {
    setMode(next);
    setOpen(true);
  }, []);

  const closeAuth = useCallback(() => setOpen(false), []);

  // The modal surfaces whatever Error this rejects with, so ApiError's
  // friendly message reaches the user unchanged.
  const submit = useCallback(
    async (which: AuthMode, email: string, password: string) => {
      const call = which === "signup" ? api.signup : api.login;
      await call(email, password);
      await refresh();
    },
    [refresh],
  );

  const value = useMemo(
    () => ({ openAuth, closeAuth, isOpen }),
    [openAuth, closeAuth, isOpen],
  );

  return (
    <AuthModalContext.Provider value={value}>
      {children}
      <AuthModal
        open={isOpen}
        onOpenChange={setOpen}
        mode={mode}
        onModeChange={setMode}
        onSubmit={submit}
      />
    </AuthModalContext.Provider>
  );
}

export function useAuthModal(): AuthModalValue {
  const value = useContext(AuthModalContext);
  if (!value) throw new Error("useAuthModal must be used inside AuthModalProvider");
  return value;
}
