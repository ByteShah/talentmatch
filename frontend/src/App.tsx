import { useEffect, useState } from 'react';

type Config = { apiUrl: string; stage: string };
type Health = { status: string; stage: string; version: string; time: string };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/config.json')
      .then((r) => r.json() as Promise<Config>)
      .then((cfg) => fetch(`${cfg.apiUrl}/v1/health`))
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`);
        return r.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main style={{ fontFamily: 'system-ui', padding: 24 }}>
      <h1>TalentMatch</h1>
      <p>Path: {window.location.pathname}</p>
      {error && <p style={{ color: 'crimson' }}>API error: {error}</p>}
      {!error && !health && <p>Checking API…</p>}
      {health && <p>API {health.status} · {health.stage} · v{health.version}</p>}
    </main>
  );
}