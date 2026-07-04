// Copyright (C) 2026 Luke Brewerton
// SPDX-License-Identifier: AGPL-3.0-or-later
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import type { CV } from "../types";

async function fetchCVs(): Promise<CV[]> {
  const res = await fetch("/api/cvs");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function uploadCV(file: File): Promise<CV> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/cvs", { method: "POST", body: form });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function setDefault(id: string): Promise<CV> {
  const res = await fetch(`/api/cvs/${id}/default`, { method: "PUT" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function rescoreCV(id: string): Promise<{ enqueued: number }> {
  const res = await fetch(`/api/cvs/${id}/rescore`, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export default function CVs() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { data: cvs, isLoading } = useQuery({ queryKey: ["cvs"], queryFn: fetchCVs });

  const [rescoreMsg, setRescoreMsg] = useState<string | null>(null);

  const defaultMut = useMutation({
    mutationFn: setDefault,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cvs"] }),
  });

  const rescoreMut = useMutation({
    mutationFn: rescoreCV,
    onSuccess: (data) => {
      setRescoreMsg(`Enqueued scoring for ${data.enqueued} jobs. Scores will appear as they complete.`);
      setTimeout(() => setRescoreMsg(null), 6000);
    },
  });

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const cv = await uploadCV(file);
      qc.invalidateQueries({ queryKey: ["cvs"] });
      setSuccess(`CV "${cv.name}" uploaded and parsed. Scoring all jobs in the background…`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Upload CV</h2>
        <p className="mb-3 text-xs text-slate-500">
          Accepted formats: <code>.txt</code>, <code>.pdf</code>, <code>.docx</code>.
          The CV is parsed by AI to extract skills, roles, and a summary.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".txt,.pdf,.docx"
          onChange={handleFile}
          disabled={uploading}
          className="block text-sm text-slate-600 file:mr-3 file:rounded file:border-0 file:bg-teal-50 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-teal-700 hover:file:bg-teal-100 disabled:opacity-50"
        />
        {uploading && (
          <p className="mt-2 text-xs text-slate-400">
            Uploading and parsing… (this calls the LLM — may take a moment)
          </p>
        )}
        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        {success && <p className="mt-2 text-xs text-teal-700">{success}</p>}
      </div>

      {rescoreMsg && (
        <p className="text-xs text-teal-700 bg-teal-50 border border-teal-200 rounded px-3 py-2">
          {rescoreMsg}
        </p>
      )}

      {isLoading && <p className="text-slate-500">Loading CVs…</p>}

      {cvs && cvs.length === 0 && (
        <p className="text-sm text-slate-400">No CVs uploaded yet.</p>
      )}

      {cvs &&
        cvs.map((cv) => (
          <div
            key={cv.id}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-semibold text-slate-800">
                  {cv.name}
                  {cv.is_default && (
                    <span className="ml-2 rounded-full bg-teal-50 px-2 py-0.5 text-xs text-teal-700 border border-teal-200">
                      Default
                    </span>
                  )}
                </h3>
                <p className="text-xs text-slate-400">v{cv.version}</p>
              </div>
              <div className="flex gap-3 items-center">
                {!cv.is_default && (
                  <button
                    onClick={() => defaultMut.mutate(cv.id)}
                    className="text-xs text-teal-600 hover:underline"
                  >
                    Set as default
                  </button>
                )}
                <button
                  onClick={() => rescoreMut.mutate(cv.id)}
                  disabled={rescoreMut.isPending}
                  className="text-xs text-slate-500 hover:text-slate-700 disabled:opacity-50"
                >
                  {rescoreMut.isPending ? "Enqueuing…" : "Re-score jobs"}
                </button>
              </div>
            </div>

            <div className="mt-3 space-y-3">
              {cv.parsed.summary && (
                <div>
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                    Summary
                  </p>
                  <p className="text-sm text-slate-600">{cv.parsed.summary}</p>
                </div>
              )}

              {Array.isArray(cv.parsed.skills) && cv.parsed.skills.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                    Skills
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {cv.parsed.skills.map((s) => (
                      <span
                        key={s}
                        className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {Array.isArray(cv.parsed.roles) && cv.parsed.roles.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                    Roles
                  </p>
                  <ul className="list-disc list-inside text-sm text-slate-600">
                    {cv.parsed.roles.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {cv.parsed.years_experience != null && (
                <p className="text-xs text-slate-400">
                  {cv.parsed.years_experience} year
                  {cv.parsed.years_experience !== 1 ? "s" : ""} of experience
                </p>
              )}
            </div>
          </div>
        ))}
    </div>
  );
}
