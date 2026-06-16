import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { Job, JobDetail, JobsPage } from "../types";

const REMOTE_OPTIONS = [
  { value: "", label: "All" },
  { value: "remote", label: "Remote" },
  { value: "remote_first", label: "Remote-first" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "Onsite" },
  { value: "unknown", label: "Unknown" },
];

async function fetchJobs(
  minFit: number | null,
  remoteMode: string,
  salaryDisclosed: boolean | null,
): Promise<JobsPage> {
  const params = new URLSearchParams({ page_size: "100" });
  if (minFit !== null) params.set("min_fit", String(minFit));
  if (remoteMode) params.set("remote_mode", remoteMode);
  if (salaryDisclosed !== null) params.set("salary_disclosed", String(salaryDisclosed));
  const res = await fetch(`/api/jobs?${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchJob(id: string): Promise<JobDetail> {
  const res = await fetch(`/api/jobs/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function salaryLabel(job: Job): string {
  if (!job.salary_disclosed) return "Not disclosed";
  if (job.salary_min == null && job.salary_max == null) return "Not disclosed";
  const fmt = (n: number) =>
    new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: job.salary_currency ?? "GBP",
      maximumFractionDigits: 0,
    }).format(n);
  if (job.salary_min != null && job.salary_max != null && job.salary_min !== job.salary_max) {
    return `${fmt(job.salary_min)} – ${fmt(job.salary_max)}`;
  }
  return fmt(job.salary_min ?? job.salary_max!);
}

function remoteLabel(mode: string): string {
  return (
    ({ remote: "Remote", remote_first: "Remote-first", hybrid: "Hybrid", onsite: "Onsite" } as Record<
      string,
      string
    >)[mode] ?? "Unknown"
  );
}

function fitBadge(score: number | null) {
  if (score === null)
    return <span className="text-slate-300 text-xs">—</span>;
  const colour =
    score >= 80
      ? "bg-teal-50 text-teal-700 border-teal-200"
      : score >= 50
        ? "bg-amber-50 text-amber-700 border-amber-200"
        : "bg-red-50 text-red-600 border-red-200";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${colour}`}>
      {score}
    </span>
  );
}

const FLAG_LABELS: Record<string, string> = {
  stretch_role: "Stretch",
  missing_must_have: "Missing must-have",
  below_salary_target: "Below salary",
  seniority_mismatch: "Seniority mismatch",
  remote_mismatch: "Remote mismatch",
};

function JobDetailPanel({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end bg-black/30">
      <div className="flex h-full w-full max-w-lg flex-col bg-white shadow-xl overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 className="font-semibold text-slate-800">Job detail</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 text-xl leading-none"
          >
            ×
          </button>
        </div>

        {isLoading && <p className="p-5 text-slate-500">Loading…</p>}
        {isError && <p className="p-5 text-red-600">Failed to load job detail.</p>}

        {data && (
          <div className="p-5 space-y-5">
            <div>
              <a
                href={data.url}
                target="_blank"
                rel="noreferrer"
                className="text-lg font-semibold text-teal-700 hover:underline"
              >
                {data.title}
              </a>
              <p className="text-sm text-slate-500">
                {data.company}
                {data.location ? ` · ${data.location}` : ""}
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                {remoteLabel(data.remote_mode)}
              </span>
              {data.fit_score !== null && fitBadge(data.fit_score)}
            </div>

            {data.flags && data.flags.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                  Flags
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {data.flags.map((f) => (
                    <span
                      key={f}
                      className="rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-xs text-amber-700"
                    >
                      {FLAG_LABELS[f] ?? f}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {data.rationale && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                  Fit assessment
                </p>
                <p className="text-sm text-slate-600">{data.rationale}</p>
              </div>
            )}

            {data.matched_skills && data.matched_skills.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                  Matched skills
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {data.matched_skills.map((s) => (
                    <span
                      key={s}
                      className="rounded-full bg-teal-50 border border-teal-200 px-2 py-0.5 text-xs text-teal-700"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {data.gaps && data.gaps.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                  Gaps
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {data.gaps.map((g) => (
                    <span
                      key={g}
                      className="rounded-full bg-red-50 border border-red-200 px-2 py-0.5 text-xs text-red-600"
                    >
                      {g}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Jobs() {
  const [minFit, setMinFit] = useState<number | null>(null);
  const [remoteMode, setRemoteMode] = useState("");
  const [salaryDisclosed, setSalaryDisclosed] = useState<boolean | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["jobs", minFit, remoteMode, salaryDisclosed],
    queryFn: () => fetchJobs(minFit, remoteMode, salaryDisclosed),
  });

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600 font-medium">Min fit:</label>
          <input
            type="number"
            min={0}
            max={100}
            placeholder="0–100"
            value={minFit ?? ""}
            onChange={(e) => {
              const v = e.target.value;
              setMinFit(v === "" ? null : Math.max(0, Math.min(100, parseInt(v, 10))));
            }}
            className="w-20 rounded border border-slate-200 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
          />
          {minFit !== null && (
            <button onClick={() => setMinFit(null)} className="text-xs text-slate-400 hover:text-slate-600">
              Clear
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600 font-medium">Remote:</label>
          <select
            value={remoteMode}
            onChange={(e) => setRemoteMode(e.target.value)}
            className="rounded border border-slate-200 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
          >
            {REMOTE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600 font-medium">Salary:</label>
          <select
            value={salaryDisclosed === null ? "" : String(salaryDisclosed)}
            onChange={(e) => {
              const v = e.target.value;
              setSalaryDisclosed(v === "" ? null : v === "true");
            }}
            className="rounded border border-slate-200 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
          >
            <option value="">All</option>
            <option value="true">Disclosed only</option>
            <option value="false">Not disclosed</option>
          </select>
        </div>
      </div>

      {isLoading && <p className="text-slate-500">Loading jobs…</p>}
      {isError && <p className="text-red-600">Failed to load jobs.</p>}

      {data && data.items.length === 0 && (
        <p className="text-slate-500">
          {minFit !== null || remoteMode || salaryDisclosed !== null
            ? "No jobs match the current filters."
            : <>No jobs yet. Run{" "}<code className="rounded bg-slate-100 px-1">make fetch SOURCE=adzuna</code> to populate.</>}
        </p>
      )}

      {data && data.items.length > 0 && (
        <>
          <p className="mb-2 text-xs text-slate-400">{data.total} job{data.total !== 1 ? "s" : ""}</p>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Company</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Remote</th>
                  <th className="px-4 py-3">Salary</th>
                  <th className="px-4 py-3">Fit</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((job) => (
                  <tr
                    key={job.id}
                    className="border-b border-slate-50 transition-colors hover:bg-slate-50 cursor-pointer"
                    onClick={() => setSelectedJobId(job.id)}
                  >
                    <td className="px-4 py-3 font-medium">
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-teal-600 hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {job.title}
                      </a>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{job.company}</td>
                    <td className="px-4 py-3 text-slate-500">{job.location ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                        {remoteLabel(job.remote_mode)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      <span className={job.salary_disclosed ? "" : "italic text-slate-400"}>
                        {salaryLabel(job)}
                      </span>
                    </td>
                    <td className="px-4 py-3">{fitBadge(job.fit_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {selectedJobId && (
        <JobDetailPanel jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />
      )}
    </>
  );
}
