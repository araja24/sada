import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuthModal } from "../state/AuthModalContext";
import type { AuthMode } from "@/components/ui/auth-modal";

/**
 * Auth moved from a full route to a modal, but /login and /signup are links
 * people may already have bookmarked. Keep them working: open the modal on
 * the right face, then hand the user to the welcome route underneath it.
 */
export default function AuthRedirect({ mode }: { mode: AuthMode }) {
  const { openAuth } = useAuthModal();

  useEffect(() => {
    openAuth(mode);
  }, [openAuth, mode]);

  return <Navigate to="/" replace />;
}
