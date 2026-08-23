"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body>
        <main className="error-page">
          <h1>CommonsGate could not start.</h1>
          <p>The failure is visible; no fallback is being presented as live evidence.</p>
          <button className="button primary" type="button" onClick={() => reset()}>Try again</button>
        </main>
      </body>
    </html>
  );
}
