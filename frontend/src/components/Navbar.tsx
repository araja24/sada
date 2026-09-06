import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../state/SessionContext";

export default function Navbar() {
  const navigate = useNavigate();
  const { user, loading, logout } = useSession();

  function goToAttempts() {
    navigate("/");
    // The recent list lives on the welcome route; give it a frame to render.
    requestAnimationFrame(() => {
      const box = document.getElementById("recent-attempts");
      if (box) box.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  return (
    <nav className="navbar" aria-label="Primary">
      <div className="navbar-inner">
        <Link className="wordmark" to="/" aria-label="Sada home">
          صدى<span>Sada</span>
        </Link>
        <div className="navbar-links">
          <button type="button" className="navlink" onClick={() => navigate("/reciters")}>
            Practice
          </button>
          <button type="button" className="navlink" onClick={goToAttempts}>
            My attempts
          </button>
          <span className="account-nav" hidden={loading}>
            {user ? (
              <>
                <span className="muted">{user.email}</span>
                <button type="button" className="btn btn-quiet back-btn" onClick={() => void logout()}>
                  Log out
                </button>
              </>
            ) : (
              <>
                <button type="button" className="btn btn-quiet back-btn" onClick={() => navigate("/login")}>
                  Log in
                </button>
                <button type="button" className="btn btn-quiet back-btn" onClick={() => navigate("/signup")}>
                  Sign up
                </button>
              </>
            )}
          </span>
        </div>
      </div>
    </nav>
  );
}
