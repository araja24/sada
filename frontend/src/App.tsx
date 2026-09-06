import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import { SessionProvider } from "./state/SessionContext";
import { AuthModalProvider } from "./state/AuthModalContext";
import Welcome from "./routes/Welcome";
import AuthRedirect from "./routes/AuthRedirect";
import Reciters from "./routes/Reciters";
import PassageRoute from "./routes/Passage";
import Record from "./routes/Record";
import Results from "./routes/Results";

export default function App() {
  return (
    <SessionProvider>
      <AuthModalProvider>
        <Navbar />
        {/* Clearance for the floating nav lives on #app in styles.css, since
            an ID selector outranks any Tailwind padding utility. */}
        <main id="app">
          <Routes>
            <Route path="/" element={<Welcome />} />
            <Route path="/login" element={<AuthRedirect mode="login" />} />
            <Route path="/signup" element={<AuthRedirect mode="signup" />} />
            <Route path="/reciters" element={<Reciters />} />
            <Route path="/verses" element={<PassageRoute />} />
            <Route path="/record" element={<Record />} />
            <Route path="/results/:attemptId" element={<Results />} />
          </Routes>
        </main>
        <Footer />
      </AuthModalProvider>
    </SessionProvider>
  );
}
