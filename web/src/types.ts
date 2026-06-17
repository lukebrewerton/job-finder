export type Job = {
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
  source_id: string;
  fit_score: number | null;
  flags: string[] | null;
  status: string | null;
  applied_at: string | null;
};

export type JobDetail = Job & {
  matched_skills: string[] | null;
  gaps: string[] | null;
  rationale: string | null;
};

export type JobsPage = {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
};

export type Profile = {
  id: string;
  user_id: string;
  name: string;
  canonical_role: string;
  seniority: string;
  title_variations: string[];
  remote_modes: string[];
  require_salary: boolean;
  min_salary: number | null;
  currency: string;
  locations: string[] | null;
  active: boolean;
  exclude_entry_level: boolean;
};

export type AuthUser = {
  id: string;
  email: string;
  name: string;
};

export type Source = {
  id: string;
  type: string;
  name: string;
  config: Record<string, unknown>;
  enabled: boolean;
  cadence_minutes: number;
  authority: number;
  last_run_at: string | null;
};

export type CVParsed = {
  skills: string[];
  roles: string[];
  years_experience: number;
  summary: string;
};

export type CV = {
  id: string;
  user_id: string;
  name: string;
  parsed: CVParsed;
  version: number;
  is_default: boolean;
};
