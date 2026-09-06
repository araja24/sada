import { useNavigate } from "react-router-dom";
import { AudioLines, Sparkles } from "lucide-react";
import { InviteCard } from "@/components/ui/invite-card";
import RecentAttempts from "../components/RecentAttempts";

export default function Welcome() {
  const navigate = useNavigate();

  return (
    <section className="step" aria-labelledby="welcome-title">
      <h1 id="welcome-title" className="sr-only">
        Recite like your favourite reciter
      </h1>
      <div className="flex justify-center py-6">
        <InviteCard
          title="Recite like your favourite reciter"
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
        />
      </div>
      <RecentAttempts />
    </section>
  );
}
