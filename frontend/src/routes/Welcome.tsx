import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AudioLines, Sparkles } from "lucide-react";
import { InviteCard } from "@/components/ui/invite-card";
import RecentAttempts from "../components/RecentAttempts";

const DISMISS_KEY = "sada.invite.dismissed";

/** Storage can throw in private windows, so every access is guarded. */
function readDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

function writeDismissed() {
  try {
    localStorage.setItem(DISMISS_KEY, "1");
  } catch {
    // A viewer who blocks site data just sees the card again next visit.
  }
}

export default function Welcome() {
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(readDismissed);

  if (!dismissed) {
    return (
      <section className="step" aria-labelledby="welcome-title">
        <h1 id="welcome-title" className="sr-only">
          Echo a reciter's style
        </h1>
        <div className="flex justify-center py-6">
          <InviteCard
            title="You're invited to echo a reciter's style"
            features={[
              {
                icon: AudioLines,
                title: "Style, not correctness",
                description:
                  "Melody, pacing, tone and elongation timing, compared to a reciter you choose.",
              },
              {
                icon: Sparkles,
                title: "Located, specific tips",
                description:
                  "Per-verse scores and a pitch contour you can read against the reference.",
              },
            ]}
            footnote={
              <>
                Sada is a practice companion, not a tajweed or correctness
                checker. Scores are guidance, not a verdict.
              </>
            }
            primaryLabel="Start practicing"
            onPrimary={() => navigate("/reciters")}
            secondaryLabel="Maybe later"
            onSecondary={() => {
              writeDismissed();
              setDismissed(true);
            }}
          />
        </div>
        <RecentAttempts />
      </section>
    );
  }

  return (
    <section className="step" aria-labelledby="welcome-title">
      <h1 id="welcome-title">Echo a reciter's style</h1>
      <p className="lede">
        Sada listens to how you recite Surah Al-Fatiha and compares the{" "}
        <em>style</em> of your delivery (melody, pacing, tone, and elongation
        timing) to a professional reciter you choose. It is a practice companion,
        not a correctness or tajweed checker.
      </p>
      <button className="btn btn-primary" onClick={() => navigate("/reciters")}>
        Start practicing
      </button>
      <RecentAttempts />
    </section>
  );
}
