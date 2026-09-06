import { useEffect, useRef } from "react";

export default function ErrorBanner({ message }: { message: string | null }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (message && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [message]);

  if (!message) return null;
  return (
    <div className="error-banner" role="alert" ref={ref}>
      {message}
    </div>
  );
}
