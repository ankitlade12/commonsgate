"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="error-page">
      <p className="eyebrow">Recoverable interface error</p>
      <h1>The evidence view could not load.</h1>
      <p>No allocation state was changed. Retry the view or inspect the API health endpoint.</p>
      <button className="button primary" type="button" onClick={() => reset()}>Try again</button>
    </main>
  );
}
