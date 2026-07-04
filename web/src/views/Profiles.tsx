// Copyright (C) 2026 Luke Brewerton
// SPDX-License-Identifier: AGPL-3.0-or-later
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { Profile } from "../types";

const SENIORITY = ["junior", "mid", "senior", "lead", "staff", "principal"];
const REMOTE_MODES = ["remote", "remote_first", "hybrid", "onsite"];

async function fetchProfiles(): Promise<Profile[]> {
  const res = await fetch("/api/profiles");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function createProfile(body: object): Promise<Profile> {
  const res = await fetch("/api/profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function updateVariations(id: string, variations: string[]): Promise<Profile> {
  const res = await fetch(`/api/profiles/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title_variations: variations }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function updateProfile(id: string, body: object): Promise<Profile> {
  const res = await fetch(`/api/profiles/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function deleteProfile(id: string): Promise<void> {
  const res = await fetch(`/api/profiles/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

function TitleChips({
  profile,
  onSaved,
}: {
  profile: Profile;
  onSaved: () => void;
}) {
  const [chips, setChips] = useState<string[]>(profile.title_variations);
  const [newTitle, setNewTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const dirty = JSON.stringify(chips) !== JSON.stringify(profile.title_variations);

  const remove = (i: number) => setChips(chips.filter((_, idx) => idx !== i));
  const add = () => {
    const t = newTitle.trim();
    if (t && !chips.includes(t)) setChips([...chips, t]);
    setNewTitle("");
  };

  const save = async () => {
    setSaving(true);
    try {
      await updateVariations(profile.id, chips);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-2">
      <p className="mb-1 text-xs font-medium text-slate-500 uppercase tracking-wide">
        Title variations
      </p>
      <div className="flex flex-wrap gap-1.5">
        {chips.map((t, i) => (
          <span
            key={i}
            className="flex items-center gap-1 rounded-full bg-teal-50 px-2.5 py-0.5 text-xs text-teal-700 border border-teal-200"
          >
            {t}
            <button
              onClick={() => remove(i)}
              className="ml-0.5 text-teal-400 hover:text-teal-700"
              aria-label={`Remove ${t}`}
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="mt-2 flex gap-2">
        <input
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Add a title…"
          className="flex-1 rounded border border-slate-200 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-teal-400"
        />
        <button
          onClick={add}
          className="rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200"
        >
          Add
        </button>
        {dirty && (
          <button
            onClick={save}
            disabled={saving}
            className="rounded bg-teal-600 px-3 py-1 text-xs text-white hover:bg-teal-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        )}
      </div>
    </div>
  );
}

function CreateForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [seniority, setSeniority] = useState("senior");
  const [remoteModes, setRemoteModes] = useState<string[]>(["remote", "remote_first"]);
  const [excludeEntryLevel, setExcludeEntryLevel] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const toggleMode = (mode: string) =>
    setRemoteModes((prev) =>
      prev.includes(mode) ? prev.filter((m) => m !== mode) : [...prev, mode],
    );

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !role.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createProfile({
        name,
        canonical_role: role,
        seniority,
        remote_modes: remoteModes,
        exclude_entry_level: excludeEntryLevel,
      });
      setName("");
      setRole("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create profile.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="mb-4 text-sm font-semibold text-slate-700">New profile</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs text-slate-500">Profile name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Cloud Platform"
            required
            className="w-full rounded border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-500">Canonical role</label>
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="e.g. Cloud Platform Engineer"
            required
            className="w-full rounded border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-500">Seniority</label>
          <select
            value={seniority}
            onChange={(e) => setSeniority(e.target.value)}
            className="w-full rounded border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-teal-400"
          >
            {SENIORITY.map((s) => (
              <option key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-500">Remote preference</label>
          <div className="flex flex-wrap gap-2 pt-1">
            {REMOTE_MODES.map((m) => (
              <label key={m} className="flex items-center gap-1 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={remoteModes.includes(m)}
                  onChange={() => toggleMode(m)}
                  className="accent-teal-600"
                />
                {m.replace("_", "-")}
              </label>
            ))}
          </div>
        </div>
        <div className="sm:col-span-2">
          <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={excludeEntryLevel}
              onChange={(e) => setExcludeEntryLevel(e.target.checked)}
              className="accent-teal-600"
            />
            Exclude entry-level &amp; trainee roles (junior, trainee, graduate, apprentice, intern)
          </label>
        </div>
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      <div className="mt-4 flex items-center gap-2">
        <button
          type="submit"
          disabled={creating}
          className="rounded bg-teal-600 px-4 py-1.5 text-sm text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {creating ? "Creating… (expanding titles via AI)" : "Create profile"}
        </button>
        {creating && (
          <span className="text-xs text-slate-400">This calls the LLM — may take a moment.</span>
        )}
      </div>
    </form>
  );
}

function ProfileCard({
  profile,
  onRefresh,
  onDelete,
}: {
  profile: Profile;
  onRefresh: () => void;
  onDelete: () => void;
}) {
  const qc = useQueryClient();

  const toggleEntryLevel = useMutation({
    mutationFn: (val: boolean) =>
      updateProfile(profile.id, { exclude_entry_level: val }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profiles"] }),
  });

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-slate-800">{profile.name}</h3>
          <p className="text-sm text-slate-500">
            {profile.canonical_role} · {profile.seniority}
            {!profile.active && (
              <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-400">
                inactive
              </span>
            )}
          </p>
        </div>
        <button onClick={onDelete} className="text-xs text-slate-400 hover:text-red-500">
          Delete
        </button>
      </div>
      <div className="mt-3">
        <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
          <input
            type="checkbox"
            checked={profile.exclude_entry_level}
            onChange={(e) => toggleEntryLevel.mutate(e.target.checked)}
            className="accent-teal-600"
            disabled={toggleEntryLevel.isPending}
          />
          Exclude entry-level &amp; trainee roles
        </label>
      </div>
      <TitleChips profile={profile} onSaved={onRefresh} />
    </div>
  );
}

export default function Profiles() {
  const qc = useQueryClient();
  const { data: profiles, isLoading } = useQuery({
    queryKey: ["profiles"],
    queryFn: fetchProfiles,
  });

  const deleteMut = useMutation({
    mutationFn: deleteProfile,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profiles"] }),
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["profiles"] });

  return (
    <div className="space-y-6">
      <CreateForm onCreated={refresh} />

      {isLoading && <p className="text-slate-500">Loading profiles…</p>}

      {profiles && profiles.length === 0 && (
        <p className="text-slate-400 text-sm">No profiles yet. Create one above.</p>
      )}

      {profiles &&
        profiles.map((p) => (
          <ProfileCard key={p.id} profile={p} onRefresh={refresh} onDelete={() => deleteMut.mutate(p.id)} />
        ))}
    </div>
  );
}
