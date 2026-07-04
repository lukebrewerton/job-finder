// Copyright (C) 2026 Luke Brewerton
// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Source } from "../types";

const ATS_TYPES = ["greenhouse", "lever", "ashby", "jsonld"] as const;
const ALL_TYPES = ["adzuna", "reed", "himalayas", "remotive", "remoteok", "hn_whoishiring", ...ATS_TYPES] as const;

async function fetchSources(): Promise<Source[]> {
  const res = await fetch("/api/sources");
  if (!res.ok) throw new Error("Failed to load sources");
  return res.json();
}

async function createSource(body: object): Promise<Source> {
  const res = await fetch("/api/sources", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function deleteSource(id: string): Promise<void> {
  const res = await fetch(`/api/sources/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}

async function updateSource(id: string, body: object): Promise<Source> {
  const res = await fetch(`/api/sources/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function toggleEnabled(id: string, enabled: boolean): Promise<Source> {
  return updateSource(id, { enabled });
}

async function runNow(id: string): Promise<{ task_id: string }> {
  const res = await fetch(`/api/admin/sources/${id}/run`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

const CONFIG_HELP: Record<string, { key: string; label: string; placeholder: string }[]> = {
  greenhouse: [{ key: "board_token", label: "Board token", placeholder: "tailscale" }],
  lever: [{ key: "board_token", label: "Board token", placeholder: "acme-corp" }],
  ashby: [{ key: "board_token", label: "Board token", placeholder: "linear" }],
  jsonld: [
    { key: "url", label: "Careers URL", placeholder: "https://acme.com/careers" },
    { key: "company", label: "Company name", placeholder: "Acme Corp" },
  ],
};

function AddSourceForm({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [type, setType] = useState<string>("greenhouse");
  const [name, setName] = useState("");
  const [cadence, setCadence] = useState(60);
  const [configFields, setConfigFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createSource,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sources"] });
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  const configDefs = CONFIG_HELP[type] ?? [];
  const isAts = (ATS_TYPES as readonly string[]).includes(type);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const config: Record<string, string> = {};
    for (const def of configDefs) {
      if (configFields[def.key]) config[def.key] = configFields[def.key];
    }
    mutation.mutate({
      type,
      name: name || type,
      config,
      enabled: true,
      cadence_minutes: cadence,
      authority: isAts ? 10 : 0,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-lg p-5 mb-6 space-y-4">
      <h3 className="font-semibold text-slate-800">Add source</h3>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Type</label>
          <select
            value={type}
            onChange={(e) => { setType(e.target.value); setConfigFields({}); }}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          >
            {ALL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Display name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={type}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
      </div>

      {configDefs.map((def) => (
        <div key={def.key}>
          <label className="block text-xs font-medium text-slate-600 mb-1">{def.label}</label>
          <input
            type="text"
            value={configFields[def.key] ?? ""}
            onChange={(e) => setConfigFields((prev) => ({ ...prev, [def.key]: e.target.value }))}
            placeholder={def.placeholder}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm font-mono"
          />
        </div>
      ))}

      <div>
        <label className="block text-xs font-medium text-slate-600 mb-1">Cadence (minutes)</label>
        <input
          type="number"
          value={cadence}
          onChange={(e) => setCadence(Number(e.target.value))}
          min={1}
          className="w-32 border border-slate-300 rounded px-2 py-1.5 text-sm"
        />
      </div>

      {isAts && (
        <p className="text-xs text-teal-700 bg-teal-50 border border-teal-200 rounded px-3 py-2">
          ATS source — will win dedup over aggregators (authority 10).
        </p>
      )}

      {error && <p className="text-xs text-red-600">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={mutation.isPending}
          className="bg-teal-600 hover:bg-teal-700 text-white text-sm px-4 py-1.5 rounded disabled:opacity-50"
        >
          {mutation.isPending ? "Adding…" : "Add source"}
        </button>
        <button type="button" onClick={onClose} className="text-sm text-slate-500 hover:text-slate-700 px-3 py-1.5">
          Cancel
        </button>
      </div>
    </form>
  );
}

function EditSourceForm({ source, onClose }: { source: Source; onClose: () => void }) {
  const qc = useQueryClient();
  const configDefs = CONFIG_HELP[source.type] ?? [];
  const [name, setName] = useState(source.name);
  const [cadence, setCadence] = useState(source.cadence_minutes);
  const [configFields, setConfigFields] = useState<Record<string, string>>(
    Object.fromEntries(configDefs.map((d) => [d.key, String(source.config[d.key] ?? "")])),
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (body: object) => updateSource(source.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sources"] });
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const config: Record<string, string> = {};
    for (const def of configDefs) {
      if (configFields[def.key]) config[def.key] = configFields[def.key];
    }
    mutation.mutate({ name, cadence_minutes: cadence, config });
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-slate-200 rounded-lg p-5 mb-6 space-y-4">
      <h3 className="font-semibold text-slate-800">
        Edit source
        <span className="ml-2 font-mono text-sm font-normal text-slate-400">{source.type}</span>
      </h3>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Display name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Cadence (minutes)</label>
          <input
            type="number"
            value={cadence}
            onChange={(e) => setCadence(Number(e.target.value))}
            min={1}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
      </div>

      {configDefs.map((def) => (
        <div key={def.key}>
          <label className="block text-xs font-medium text-slate-600 mb-1">{def.label}</label>
          <input
            type="text"
            value={configFields[def.key] ?? ""}
            onChange={(e) => setConfigFields((prev) => ({ ...prev, [def.key]: e.target.value }))}
            placeholder={def.placeholder}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm font-mono"
          />
        </div>
      ))}

      {error && <p className="text-xs text-red-600">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={mutation.isPending}
          className="bg-teal-600 hover:bg-teal-700 text-white text-sm px-4 py-1.5 rounded disabled:opacity-50"
        >
          {mutation.isPending ? "Saving…" : "Save changes"}
        </button>
        <button type="button" onClick={onClose} className="text-sm text-slate-500 hover:text-slate-700 px-3 py-1.5">
          Cancel
        </button>
      </div>
    </form>
  );
}

function SourceRow({ source, onEdit }: { source: Source; onEdit: (s: Source) => void }) {
  const qc = useQueryClient();
  const [runStatus, setRunStatus] = useState<string | null>(null);

  const toggleMutation = useMutation({
    mutationFn: () => toggleEnabled(source.id, !source.enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteSource(source.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });

  async function handleRunNow() {
    try {
      setRunStatus("queued");
      await runNow(source.id);
      setRunStatus("enqueued ✓");
      setTimeout(() => setRunStatus(null), 3000);
    } catch {
      setRunStatus("error");
    }
  }

  const authorityBadge =
    source.authority > 0 ? (
      <span className="text-xs bg-teal-100 text-teal-700 px-1.5 py-0.5 rounded font-medium">
        ATS
      </span>
    ) : null;

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="px-4 py-3 text-sm font-mono text-slate-700">{source.type}</td>
      <td className="px-4 py-3 text-sm text-slate-800">
        <span className="font-medium">{source.name}</span>{" "}
        {authorityBadge}
      </td>
      <td className="px-4 py-3 text-xs text-slate-500 font-mono max-w-xs truncate">
        {Object.entries(source.config)
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ") || "—"}
      </td>
      <td className="px-4 py-3 text-sm text-center">
        <button
          onClick={() => toggleMutation.mutate()}
          className={[
            "text-xs px-2 py-0.5 rounded-full font-medium",
            source.enabled
              ? "bg-green-100 text-green-700 hover:bg-green-200"
              : "bg-slate-100 text-slate-500 hover:bg-slate-200",
          ].join(" ")}
        >
          {source.enabled ? "enabled" : "disabled"}
        </button>
      </td>
      <td className="px-4 py-3 text-sm text-slate-500 text-right">
        {source.cadence_minutes}m
      </td>
      <td className="px-4 py-3 text-xs text-slate-400">
        {source.last_run_at ? new Date(source.last_run_at).toLocaleString() : "never"}
      </td>
      <td className="px-4 py-3">
        <div className="flex gap-2 items-center justify-end">
          <button
            onClick={handleRunNow}
            className="text-xs text-teal-600 hover:text-teal-800 font-medium"
          >
            {runStatus ?? "Run now"}
          </button>
          <button
            onClick={() => onEdit(source)}
            className="text-xs text-slate-500 hover:text-slate-700"
          >
            Edit
          </button>
          <button
            onClick={() => deleteMutation.mutate()}
            className="text-xs text-red-400 hover:text-red-600"
          >
            Delete
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function Sources() {
  const [showForm, setShowForm] = useState(false);
  const [editingSource, setEditingSource] = useState<Source | null>(null);
  const { data: sources, isLoading, error } = useQuery({ queryKey: ["sources"], queryFn: fetchSources });

  if (isLoading) return <p className="text-slate-500 text-sm">Loading sources…</p>;
  if (error) return <p className="text-red-500 text-sm">Failed to load sources.</p>;

  function handleEdit(s: Source) {
    setShowForm(false);
    setEditingSource(s);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-800">Sources</h2>
        {!showForm && !editingSource && (
          <button
            onClick={() => setShowForm(true)}
            className="bg-teal-600 hover:bg-teal-700 text-white text-sm px-4 py-1.5 rounded"
          >
            Add source
          </button>
        )}
      </div>

      {showForm && <AddSourceForm onClose={() => setShowForm(false)} />}
      {editingSource && <EditSourceForm source={editingSource} onClose={() => setEditingSource(null)} />}

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-slate-50 text-xs font-medium text-slate-500 uppercase">
            <tr>
              <th className="px-4 py-2 text-left">Type</th>
              <th className="px-4 py-2 text-left">Name</th>
              <th className="px-4 py-2 text-left">Config</th>
              <th className="px-4 py-2 text-center">Status</th>
              <th className="px-4 py-2 text-right">Cadence</th>
              <th className="px-4 py-2 text-left">Last run</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sources?.map((s) => <SourceRow key={s.id} source={s} onEdit={handleEdit} />)}
            {!sources?.length && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400 text-sm">
                  No sources configured. Add one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
