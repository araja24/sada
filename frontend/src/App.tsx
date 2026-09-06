import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import { SessionProvider } from "./state/SessionContext";
import Welcome from "./routes/Welcome";

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
          <Route path="/login" element={<Placeholder name="Log in" />} />
          <Route path="/signup" element={<Placeholder name="Sign up" />} />
          <Route path="/reciters" element={<Placeholder name="Reciters" />} />
          <Route path="/verses" element={<Placeholder name="Verses" />} />
          <Route path="/record" element={<Placeholder name="Record" />} />
          <Route path="/results/:attemptId" element={<Placeholder name="Results" />} />
        </Routes>
      </main>
      <Footer />
    </SessionProvider>
  );
}
