import { useQuery } from "@tanstack/react-query";

type Ready = {
  ready: boolean;
  checks: Record<string, string>;
};

async function fetchReady(): Promise<Ready> {
  const res = await fetch("/api/ready");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export default function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["ready"],
    queryFn: fetchReady,
    refetchInterval: 5000,
  });

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-gradient-to-r from-teal-500 to-blue-600 px-8 py-6 text-white">
        <h1 className="text-2xl font-semibold tracking-tight">Job Finder</h1>
        <p className="text-sm text-white/80">Phase 0 — scaffold up and running</p>
      </header>

      <main className="mx-auto max-w-3xl px-8 py-10">
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-medium">Backend status</h2>

          {isLoading && <p className="text-slate-500">Checking…</p>}
          {isError && <p className="text-red-600">API unreachable.</p>}

          {data && (
            <ul className="space-y-2">
              {Object.entries(data.checks).map(([name, status]) => (
                <li key={name} className="flex items-center justify-between">
                  <span className="capitalize">{name}</span>
                  <span
                    className={
                      status === "ok"
                        ? "rounded-full bg-teal-100 px-3 py-0.5 text-sm text-teal-700"
                        : "rounded-full bg-red-100 px-3 py-0.5 text-sm text-red-700"
                    }
                  >
                    {status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
