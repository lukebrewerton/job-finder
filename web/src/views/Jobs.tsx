// Copyright (C) 2026 Luke Brewerton
// SPDX-License-Identifier: AGPL-3.0-or-later
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, useDeferredValue } from "react";
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
  page: number,
  minFit: number | null,
  remoteMode: string,
  salaryDisclosed: boolean | null,
  statusFilter: string | null,
  search: string,
): Promise<JobsPage> {
  const params = new URLSearchParams({ page: String(page), page_size: "50" });
  if (minFit !== null) params.set("min_fit", String(minFit));
  if (remoteMode) params.set("remote_mode", remoteMode);
  if (salaryDisclosed !== null) params.set("salary_disclosed", String(salaryDisclosed));
  if (statusFilter) params.set("status", statusFilter);
  if (search) params.set("search", search);
  const res = await fetch(`/api/jobs?${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchJob(id: string): Promise<JobDetail> {
  const res = await fetch(`/api/jobs/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function setJobState(id: string, status: string, notes: string): Promise<void> {
  const res = await fetch(`/api/jobs/${id}/state`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes: notes || null }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
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

const STATUS_BADGE: Record<string, string> = {
  shortlisted: "bg-blue-50 text-blue-700 border-blue-200",
  applied: "bg-teal-50 text-teal-700 border-teal-200",
  rejected: "bg-red-50 text-red-600 border-red-200",
  ignored: "bg-slate-100 text-slate-500 border-slate-200",
};

function statusBadge(status: string | null) {
  if (!status || status === "new") return null;
  const cls = STATUS_BADGE[status] ?? "bg-slate-100 text-slate-500 border-slate-200";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function appliedDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

const STALE_DAYS = 14;

function staleBadge(lastSeenAt: string) {
  const days = Math.floor(
    (Date.now() - new Date(lastSeenAt).getTime()) / 86_400_000,
  );
  if (days < STALE_DAYS) return null;
  return (
    <span
      title={`Last seen on this source ${days} day${days === 1 ? "" : "s"} ago — listing may have closed`}
      className="ml-1.5 rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700"
    >
      {days}d ago
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

const TRIAGE_ACTIONS = [
  { status: "shortlisted", label: "Shortlist" },
  { status: "applied", label: "Mark as applied" },
  { status: "rejected", label: "Reject" },
  { status: "ignored", label: "Ignore" },
] as const;

const TRIAGE_ACTIVE_CLS: Record<string, string> = {
  shortlisted: "bg-blue-600 text-white border-blue-600",
  applied: "bg-teal-600 text-white border-teal-600",
  rejected: "bg-red-500 text-white border-red-500",
  ignored: "bg-slate-500 text-white border-slate-500",
};

function TriageSection({
  data,
  onMutate,
  isPending,
}: {
  data: JobDetail;
  onMutate: (status: string, notes: string) => void;
  isPending: boolean;
}) {
  const current = data.status ?? "new";
  const [notes, setNotes] = useState(data.notes ?? "");

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-2">Triage</p>
        <div className="flex flex-wrap gap-2">
          {TRIAGE_ACTIONS.map(({ status, label }) => {
            const isActive = current === status;
            const activeCls = TRIAGE_ACTIVE_CLS[status];
            return (
              <button
                key={status}
                onClick={() => onMutate(isActive ? "new" : status, notes)}
                disabled={isPending}
                className={[
                  "rounded border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50",
                  isActive
                    ? activeCls
                    : "border-slate-200 text-slate-600 hover:bg-slate-50",
                ].join(" ")}
              >
                {isActive ? `✓ ${label}` : label}
                {status === "applied" && isActive && data.applied_at
                  ? ` · ${appliedDate(data.applied_at)}`
                  : ""}
              </button>
            );
          })}
        </div>
        {current !== "new" && (
          <button
            onClick={() => onMutate("new", notes)}
            disabled={isPending}
            className="mt-1.5 text-xs text-slate-400 hover:text-slate-600 disabled:opacity-50"
          >
            Reset to new
          </button>
        )}
      </div>

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">Notes</p>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => {
            if (notes !== (data.notes ?? "")) {
              onMutate(current, notes);
            }
          }}
          placeholder="Add a note…"
          rows={3}
          className="w-full rounded border border-slate-200 px-3 py-2 text-sm text-slate-700 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none"
        />
      </div>
    </div>
  );
}

function JobDetailPanel({
  jobId,
  onClose,
  onTriage,
}: {
  jobId: string;
  onClose: () => void;
  onTriage: (jobId: string, title: string, prevStatus: string, newStatus: string) => void;
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId),
  });

  const qc = useQueryClient();

  const stateMut = useMutation({
    mutationFn: ({ id, status, notes }: { id: string; status: string; notes: string }) =>
      setJobState(id, status, notes),
    onSuccess: (_result, variables) => {
      qc.invalidateQueries({ queryKey: ["job", jobId] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      if (data) {
        onTriage(jobId, data.title, data.status ?? "new", variables.status);
      }
    },
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

            <TriageSection
              data={data}
              onMutate={(status, notes) => stateMut.mutate({ id: data.id, status, notes })}
              isPending={stateMut.isPending}
            />

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

            {data.summary && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                  Role summary
                </p>
                <p className="text-sm text-slate-600">{data.summary}</p>
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

function JobsTable({
  jobs,
  onRowClick,
  showStatus,
}: {
  jobs: Job[];
  onRowClick: (id: string) => void;
  showStatus: boolean;
}) {
  const showAppliedDate = jobs.some((j) => j.applied_at != null);
  return (
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
            {showStatus && <th className="px-4 py-3">Status</th>}
            {showAppliedDate && <th className="px-4 py-3">Applied</th>}
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr
              key={job.id}
              className="border-b border-slate-50 transition-colors hover:bg-slate-50 cursor-pointer"
              onClick={() => onRowClick(job.id)}
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
                {staleBadge(job.last_seen_at)}
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
              {showStatus && (
                <td className="px-4 py-3">{statusBadge(job.status)}</td>
              )}
              {showAppliedDate && (
                <td className="px-4 py-3 text-slate-500 text-xs">
                  {job.applied_at ? appliedDate(job.applied_at) : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (p: number) => void;
}) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="mt-4 flex items-center justify-between text-sm">
      <p className="text-xs text-slate-400">
        {start}–{end} of {total} result{total !== 1 ? "s" : ""}
      </p>
      <div className="flex gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 1}
          className="rounded border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <span className="rounded border border-slate-200 px-3 py-1 text-xs text-slate-500 bg-slate-50">
          {page} / {totalPages}
        </span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="rounded border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>
  );
}

type UndoInfo = {
  jobId: string;
  jobTitle: string;
  prevStatus: string;
  newStatus: string;
};

export default function Jobs() {
  const [tab, setTab] = useState<"active" | "shortlisted" | "applied">("active");
  const [page, setPage] = useState(1);
  const [minFit, setMinFit] = useState<number | null>(null);
  const [remoteMode, setRemoteMode] = useState("");
  const [salaryDisclosed, setSalaryDisclosed] = useState<boolean | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDeferredValue(search);
  const [undoInfo, setUndoInfo] = useState<UndoInfo | null>(null);
  const undoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const qc = useQueryClient();

  useEffect(() => {
    return () => {
      if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
    };
  }, []);

  function setTabAndReset(t: "active" | "shortlisted" | "applied") {
    setTab(t);
    setPage(1);
    setSearch("");
  }
  function setMinFitAndReset(v: number | null) {
    setMinFit(v);
    setPage(1);
  }
  function setRemoteModeAndReset(v: string) {
    setRemoteMode(v);
    setPage(1);
  }
  function setSalaryDisclosedAndReset(v: boolean | null) {
    setSalaryDisclosed(v);
    setPage(1);
  }

  const statusFilter = tab === "active" ? null : tab;

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["jobs", tab, page, minFit, remoteMode, salaryDisclosed, debouncedSearch],
    queryFn: () => fetchJobs(page, minFit, remoteMode, salaryDisclosed, statusFilter, debouncedSearch),
  });

  const handleTriage = (jobId: string, title: string, prevStatus: string, newStatus: string) => {
    if (undoTimerRef.current) clearTimeout(undoTimerRef.current);

    if (newStatus === "rejected" || newStatus === "ignored") {
      setUndoInfo({ jobId, jobTitle: title, prevStatus, newStatus });
      undoTimerRef.current = setTimeout(() => {
        setUndoInfo(null);
        undoTimerRef.current = null;
      }, 5000);
    } else {
      setUndoInfo(null);
    }
  };

  const handleUndo = async () => {
    if (!undoInfo) return;
    if (undoTimerRef.current) {
      clearTimeout(undoTimerRef.current);
      undoTimerRef.current = null;
    }
    await setJobState(undoInfo.jobId, undoInfo.prevStatus, "");
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["job", undoInfo.jobId] });
    setUndoInfo(null);
  };

  const isActiveTab = tab === "active";
  const isShortlistedTab = tab === "shortlisted";

  return (
    <>
      {/* Tab switcher */}
      <div className="mb-4 flex gap-1 border-b border-slate-200">
        {(["active", "shortlisted", "applied"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTabAndReset(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-teal-600 text-teal-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t === "active" ? "Active" : t === "shortlisted" ? "Shortlisted" : "Applied"}
          </button>
        ))}
      </div>

      {/* Search — all tabs */}
      <div className="mb-4">
        <input
          type="search"
          placeholder="Search by title or company…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-sm rounded border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
        />
      </div>

      {/* Filters — only on active and shortlisted tabs */}
      {(isActiveTab || isShortlistedTab) && (
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
                setMinFitAndReset(v === "" ? null : Math.max(0, Math.min(100, parseInt(v, 10))));
              }}
              className="w-20 rounded border border-slate-200 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
            />
            {minFit !== null && (
              <button onClick={() => setMinFitAndReset(null)} className="text-xs text-slate-400 hover:text-slate-600">
                Clear
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-600 font-medium">Remote:</label>
            <select
              value={remoteMode}
              onChange={(e) => setRemoteModeAndReset(e.target.value)}
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
                setSalaryDisclosedAndReset(v === "" ? null : v === "true");
              }}
              className="rounded border border-slate-200 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400"
            >
              <option value="">All</option>
              <option value="true">Disclosed only</option>
              <option value="false">Not disclosed</option>
            </select>
          </div>
        </div>
      )}

      {isLoading && <p className="text-slate-500">Loading jobs…</p>}
      {isError && <p className="text-red-600">Failed to load jobs.</p>}

      {data && data.items.length === 0 && (
        <p className="text-slate-500">
          {tab === "applied"
            ? "No applied jobs yet. Open a job and click \"Mark as applied\"."
            : tab === "shortlisted"
              ? "No shortlisted jobs yet. Open a job and click \"Shortlist\"."
              : minFit !== null || remoteMode || salaryDisclosed !== null || debouncedSearch
                ? "No jobs match the current filters."
                : <>No jobs yet. Run{" "}<code className="rounded bg-slate-100 px-1">make fetch SOURCE=adzuna</code> to populate.</>}
        </p>
      )}

      {data && data.items.length > 0 && (
        <>
          <p className="mb-2 text-xs text-slate-400">
            {data.total} job{data.total !== 1 ? "s" : ""}
          </p>
          <JobsTable
            jobs={data.items}
            onRowClick={setSelectedJobId}
            showStatus={isActiveTab && data.items.some((j) => j.status && j.status !== "new")}
          />
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={setPage}
          />
        </>
      )}

      {selectedJobId && (
        <JobDetailPanel
          jobId={selectedJobId}
          onClose={() => setSelectedJobId(null)}
          onTriage={handleTriage}
        />
      )}

      {undoInfo && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 rounded-lg bg-slate-800 px-4 py-3 text-sm text-white shadow-lg">
          <span>
            {undoInfo.newStatus === "rejected" ? "Rejected" : "Ignored"}
            {" · "}
            <span className="max-w-xs truncate opacity-60">{undoInfo.jobTitle}</span>
          </span>
          <button
            onClick={handleUndo}
            className="rounded bg-white/20 px-2.5 py-1 text-xs font-medium hover:bg-white/30 transition-colors"
          >
            Undo
          </button>
        </div>
      )}
    </>
  );
}
