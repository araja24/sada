import { useNavigate } from "react-router-dom";
import { AnimatedNav } from "@/components/ui/navigation-menu";
import { useSession } from "../state/SessionContext";
import { useAuthModal } from "../state/AuthModalContext";

export default function Navbar() {
  const navigate = useNavigate();
  const { user, loading, logout } = useSession();
  const { openAuth } = useAuthModal();

  function goToAttempts() {
    navigate("/");
    // The recent list lives on the welcome route; give it a frame to render.
    requestAnimationFrame(() => {
      const box = document.getElementById("recent-attempts");
      if (box) box.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  const items = [
    { name: "Home", onSelect: () => navigate("/") },
    { name: "Practice", onSelect: () => navigate("/reciters") },
    { name: "My attempts", onSelect: goToAttempts },
  ];

  return (
    <AnimatedNav
      items={items}
      logo={
        <span
          className="flex items-baseline gap-1.5 text-foreground"
          aria-label="Sada home"
        >
          <span
            className="text-xl leading-none"
            style={{ fontFamily: '"Amiri Quran", serif' }}
          >
            صدى
          </span>
          <span className="text-sm font-semibold">Sada</span>
        </span>
      }
      trailing={
        loading ? null : user ? (
          <>
            <span className="hidden max-w-[11rem] truncate text-sm text-muted-foreground sm:inline">
              {user.email}
            </span>
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded-full border border-border px-3 py-1 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              Log out
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => openAuth("login")}
              className="rounded-full px-2 py-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              Log in
            </button>
            <button
              type="button"
              onClick={() => openAuth("signup")}
              className="rounded-full bg-primary px-3.5 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Sign up
            </button>
          </>
        )
      }
    />
  );
}
