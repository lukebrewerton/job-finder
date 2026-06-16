import { useQuery } from "@tanstack/react-query";

type Job = {
  id: string;
  title: string;
  company: string;
  url: string;
  location: string | null;
  remote_mode: string;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_disclosed: boolean;
};

type JobsPage = {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
};

async function fetchJobs(): Promise<JobsPage> {
  const res = await fetch("/api/jobs?page_size=100");
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
  return { remote: "Remote", remote_first: "Remote-first", hybrid: "Hybrid", onsite: "Onsite" }[
    mode
  ] ?? "Unknown";
}

export default function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["jobs"],
    queryFn: fetchJobs,
  });

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-gradient-to-r from-teal-500 to-blue-600 px-8 py-5 text-white">
        <h1 className="text-2xl font-semibold tracking-tight">Job Finder</h1>
        {data && (
          <p className="text-sm text-white/80">
            {data.total} role{data.total !== 1 ? "s" : ""}
          </p>
        )}
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8">
        {isLoading && <p className="text-slate-500">Loading jobs…</p>}
        {isError && <p className="text-red-600">Failed to load jobs.</p>}

        {data && data.items.length === 0 && (
          <p className="text-slate-500">
            No jobs yet. Run <code className="rounded bg-slate-100 px-1">make fetch SOURCE=adzuna QUERY="..."</code> to
            populate.
          </p>
        )}

        {data && data.items.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Company</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Remote</th>
                  <th className="px-4 py-3">Salary</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((job) => (
                  <tr
                    key={job.id}
                    className="border-b border-slate-50 hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium">
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-teal-600 hover:underline"
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
                      <span className={job.salary_disclosed ? "" : "text-slate-400 italic"}>
                        {salaryLabel(job)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
