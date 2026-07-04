// Copyright (C) 2026 Luke Brewerton
// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import CVs from "./views/CVs";
import Jobs from "./views/Jobs";
import Profiles from "./views/Profiles";
import Sources from "./views/Sources";
import type { AuthUser, JobsPage } from "./types";

type Tab = "jobs" | "profiles" | "cvs" | "sources";

async function fetchMe(): Promise<AuthUser | null> {
  const res = await fetch("/api/auth/me");
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchJobCount(): Promise<number> {
  const res = await fetch("/api/jobs?page_size=1");
  if (!res.ok) return 0;
  const data: JobsPage = await res.json();
  return data.total;
}

async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}

function LoginScreen() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center">
      <div className="rounded-xl border border-slate-200 bg-white p-10 shadow-sm text-center max-w-sm w-full">
        <h1 className="text-2xl font-semibold text-slate-800 mb-2">Job Finder</h1>
        <p className="text-sm text-slate-500 mb-6">Sign in to access your job dashboard.</p>
        <a
          href="/api/auth/login"
          className="inline-block rounded bg-teal-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-teal-700 transition-colors"
        >
          Sign in
        </a>
      </div>
    </div>
  );
}

export default function App() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("jobs");

  const { data: authUser, isLoading: authLoading } = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const { data: jobCount } = useQuery({
    queryKey: ["jobCount"],
    queryFn: fetchJobCount,
    enabled: authUser != null,
  });

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <p className="text-slate-400 text-sm">Loading…</p>
      </div>
    );
  }

  if (!authUser) {
    return <LoginScreen />;
  }

  const handleLogout = async () => {
    await logout();
    qc.clear();
    window.location.href = "/";
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "jobs", label: `Jobs${jobCount != null ? ` (${jobCount})` : ""}` },
    { key: "profiles", label: "Profiles" },
    { key: "cvs", label: "CVs" },
    { key: "sources", label: "Sources" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-gradient-to-r from-teal-500 to-blue-600 px-8 py-5 text-white flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Job Finder</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className="opacity-80">{authUser.name || authUser.email}</span>
          <button
            onClick={handleLogout}
            className="rounded border border-white/30 px-3 py-1 text-xs text-white/90 hover:bg-white/10 transition-colors"
          >
            Sign out
          </button>
        </div>
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
