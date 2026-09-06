import { useNavigate } from "react-router-dom";
import RecentAttempts from "../components/RecentAttempts";

export default function Welcome() {
  const navigate = useNavigate();
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
