import { getSupabaseBrowserClient } from "./supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch(path: string, init: RequestInit = {}) {
  const supabase = getSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

/** Like apiFetch, but for multipart/form-data uploads — never set
 * Content-Type manually for FormData, the browser needs to add its own
 * boundary parameter. */
export async function apiUpload(path: string, formData: FormData) {
  const supabase = getSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    body: formData,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export interface Challenge {
  id: string;
  owasp_category: string;
  title: string;
  difficulty: string;
  summary: string;
  learning_objectives: string[];
  prerequisites: string[];
  authorized_scope: string;
  required_services: string[];
  hints: string[];
  points: number;
}

export const listChallenges = (): Promise<Challenge[]> => apiFetch("/challenges");
export const getChallenge = (id: string): Promise<Challenge> => apiFetch(`/challenges/${id}`);
export const submitChallenge = (id: string, evidence: Record<string, string>) =>
  apiFetch(`/challenges/${id}/submit`, { method: "POST", body: JSON.stringify({ evidence }) });
export const myProgress = (): Promise<any[]> => apiFetch("/challenges/progress/me");

export interface Team {
  id: string;
  name: string;
  mode: string;
  created_by: string;
  created_at: string;
}

export const listMyTeams = (): Promise<Team[]> => apiFetch("/teams/mine");
export const createTeam = (name: string, mode: string): Promise<Team> =>
  apiFetch("/teams", { method: "POST", body: JSON.stringify({ name, mode }) });
export const joinTeam = (teamId: string) => apiFetch(`/teams/${teamId}/join`, { method: "POST" });
export const listTeamMembers = (teamId: string) => apiFetch(`/teams/${teamId}/members`);
export const listTeamReports = (teamId: string) => apiFetch(`/teams/${teamId}/reports`);
export const createReport = (body: {
  challenge_id: string;
  title: string;
  severity: string;
  description: string;
  team_id?: string;
}) => apiFetch("/teams/reports", { method: "POST", body: JSON.stringify(body) });
export const startTeamSession = (teamId: string, challengeId: string, mode: "attack" | "defense") =>
  apiFetch(`/teams/${teamId}/sessions`, {
    method: "POST",
    body: JSON.stringify({ challenge_id: challengeId, mode }),
  });

export interface LeaderboardEntry {
  user_id: string;
  display_name: string | null;
  total_points: number;
  challenges_completed: number;
  rank: number;
}

export const getUserLeaderboard = (): Promise<LeaderboardEntry[]> => apiFetch("/leaderboard/users");
export const getTeamLeaderboard = () => apiFetch("/leaderboard/teams");

export interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: string;
}

export const listAchievements = (): Promise<Achievement[]> => apiFetch("/achievements");
export const myAchievements = (): Promise<any[]> => apiFetch("/achievements/me");

export interface Org {
  id: string;
  name: string;
  created_at: string;
}

export const listMyOrgs = (): Promise<Org[]> => apiFetch("/orgs/mine");
export const createOrg = (name: string): Promise<Org> =>
  apiFetch("/orgs", { method: "POST", body: JSON.stringify({ name }) });

// --- Projects / Tasks ---
export const listProjects = (orgId: string) => apiFetch(`/orgs/${orgId}/projects`);
export const createProject = (orgId: string, name: string, description?: string) =>
  apiFetch(`/orgs/${orgId}/projects`, { method: "POST", body: JSON.stringify({ name, description }) });
export const listTasks = (orgId: string, projectId: string) =>
  apiFetch(`/orgs/${orgId}/projects/${projectId}/tasks`);
export const createTask = (orgId: string, projectId: string, title: string) =>
  apiFetch(`/orgs/${orgId}/projects/${projectId}/tasks`, { method: "POST", body: JSON.stringify({ title }) });
export const updateTaskStatus = (orgId: string, projectId: string, taskId: string, status: string) =>
  apiFetch(`/orgs/${orgId}/projects/${projectId}/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });

// --- Documents ---
export const listDocuments = (orgId: string) => apiFetch(`/orgs/${orgId}/documents`);
export const uploadDocument = (orgId: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiUpload(`/orgs/${orgId}/documents`, form);
};
export const downloadDocument = (orgId: string, documentId: string) =>
  apiFetch(`/orgs/${orgId}/documents/${documentId}/download`);
export const deleteDocument = (orgId: string, documentId: string) =>
  apiFetch(`/orgs/${orgId}/documents/${documentId}`, { method: "DELETE" });

// --- API keys ---
export const listApiKeys = (orgId: string) => apiFetch(`/orgs/${orgId}/api-keys`);
export const createApiKey = (orgId: string, name: string) =>
  apiFetch(`/orgs/${orgId}/api-keys`, { method: "POST", body: JSON.stringify({ name, scopes: ["read"] }) });
export const revokeApiKey = (orgId: string, keyId: string) =>
  apiFetch(`/orgs/${orgId}/api-keys/${keyId}`, { method: "DELETE" });

// --- Webhooks ---
export const listWebhooks = (orgId: string) => apiFetch(`/orgs/${orgId}/webhooks`);
export const createWebhook = (orgId: string, targetUrl: string, eventTypes: string[]) =>
  apiFetch(`/orgs/${orgId}/webhooks`, {
    method: "POST",
    body: JSON.stringify({ target_url: targetUrl, event_types: eventTypes }),
  });
export const deleteWebhook = (orgId: string, webhookId: string) =>
  apiFetch(`/orgs/${orgId}/webhooks/${webhookId}`, { method: "DELETE" });
export const testWebhook = (orgId: string, webhookId: string) =>
  apiFetch(`/orgs/${orgId}/webhooks/${webhookId}/test`, { method: "POST" });

export const getSecurityEvents = (orgId: string) => apiFetch(`/orgs/${orgId}/security/events`);
export async function downloadSecurityEventsCsv(orgId: string) {
  const supabase = getSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const res = await fetch(`${API_URL}/orgs/${orgId}/security/events/export`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `aegis-security-events-${orgId}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export const getSecurityMetrics = (orgId: string, windowHours = 24) =>
  apiFetch(`/orgs/${orgId}/security/metrics?window_hours=${windowHours}`);

export const listMyClassrooms = (): Promise<any[]> => apiFetch("/classrooms/mine");
export const createClassroom = (name: string) =>
  apiFetch("/classrooms", { method: "POST", body: JSON.stringify({ name }) });
export const createClassroomInvite = (classroomId: string) =>
  apiFetch(`/classrooms/${classroomId}/invites`, { method: "POST" });
export const createAssignment = (classroomId: string, challengeId: string) =>
  apiFetch(`/classrooms/${classroomId}/assignments`, {
    method: "POST",
    body: JSON.stringify({ challenge_id: challengeId }),
  });
export const getClassroomProgress = (classroomId: string) =>
  apiFetch(`/classrooms/${classroomId}/progress`);
