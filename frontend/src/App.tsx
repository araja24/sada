import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import { SessionProvider } from "./state/SessionContext";
import Welcome from "./routes/Welcome";
import Auth from "./routes/Auth";
import Reciters from "./routes/Reciters";
import PassageRoute from "./routes/Passage";
import Record from "./routes/Record";

function Placeholder({ name }: { name: string }) {
  return <section className="step">{name}</section>;
}

export default function App() {
  return (
    <SessionProvider>
      <Navbar />
      <main id="app">
        <Routes>
          <Route path="/" element={<Welcome />} />
          <Route path="/login" element={<Auth mode="login" />} />
          <Route path="/signup" element={<Auth mode="signup" />} />
          <Route path="/reciters" element={<Reciters />} />
          <Route path="/verses" element={<PassageRoute />} />
          <Route path="/record" element={<Record />} />
          <Route path="/results/:attemptId" element={<Placeholder name="Results" />} />
        </Routes>
      </main>
      <Footer />
    </SessionProvider>
  );
}
