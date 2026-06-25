"use client";

import { useEffect } from "react";

// Root error boundary — replaces the ROOT layout when the layout itself throws,
// so it must render its own <html>/<body> and CANNOT rely on the i18n provider,
// theme vars, or fonts (they live in the layout that just failed). Kept minimal
// and self-contained on purpose.
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, sans-serif",
          background: "#f8fafc",
          color: "#0f172a",
        }}
      >
        <div style={{ maxWidth: 420, padding: 24, textAlign: "center" }}>
          <h1 style={{ fontSize: 18, fontWeight: 600 }}>Application error</h1>
          <p style={{ fontSize: 14, color: "#475569" }}>
            A critical error prevented the app from loading. Please reload.
            {error.digest && <span style={{ display: "block", marginTop: 8, fontFamily: "monospace", fontSize: 12 }}>ref: {error.digest}</span>}
          </p>
          <button
            onClick={reset}
            style={{
              marginTop: 16,
              height: 36,
              padding: "0 16px",
              borderRadius: 6,
              border: "none",
              background: "#1e293b",
              color: "#fff",
              fontSize: 14,
              cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
