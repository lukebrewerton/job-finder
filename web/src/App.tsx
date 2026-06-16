import { useState } from "react";
import CVs from "./views/CVs";
import Jobs from "./views/Jobs";
import Profiles from "./views/Profiles";
import Sources from "./views/Sources";
import { useQuery } from "@tanstack/react-query";
import type { JobsPage } from "./types";

type Tab = "jobs" | "profiles" | "cvs" | "sources";

async function fetchJobCount(): Promise<number> {
  const res = await fetch("/api/jobs?page_size=1");
  if (!res.ok) return 0;
  const data: JobsPage = await res.json();
  return data.total;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("jobs");
  const { data: jobCount } = useQuery({ queryKey: ["jobCount"], queryFn: fetchJobCount });

  const tabs: { key: Tab; label: string }[] = [
    { key: "jobs", label: `Jobs${jobCount != null ? ` (${jobCount})` : ""}` },
    { key: "profiles", label: "Profiles" },
    { key: "cvs", label: "CVs" },
    { key: "sources", label: "Sources" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-gradient-to-r from-teal-500 to-blue-600 px-8 py-5 text-white">
        <h1 className="text-2xl font-semibold tracking-tight">Job Finder</h1>
      </header>

      <nav className="border-b border-slate-200 bg-white px-8">
        <div className="flex gap-0 max-w-7xl mx-auto">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={[
                "px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                tab === t.key
                  ? "border-teal-500 text-teal-700"
                  : "border-transparent text-slate-500 hover:text-slate-700",
              ].join(" ")}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-4 py-8">
        {tab === "jobs" && <Jobs />}
        {tab === "profiles" && <Profiles />}
        {tab === "cvs" && <CVs />}
        {tab === "sources" && <Sources />}
      </main>
    </div>
  );
}
