"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  createApiKey,
  createProject,
  createTask,
  updateTaskStatus,
  createWebhook,
  deleteDocument,
  deleteWebhook,
  downloadDocument,
  listApiKeys,
  listDocuments,
  listProjects,
  listTasks,
  listWebhooks,
  revokeApiKey,
  testWebhook,
  uploadDocument,
} from "@/lib/api";

type Tab = "projects" | "documents" | "api-keys" | "webhooks";

export default function OrgDashboardPage() {
  const params = useParams<{ id: string }>();
  const orgId = params.id;
  const [tab, setTab] = useState<Tab>("projects");
  const [error, setError] = useState<string | null>(null);

  return (
    <main className="max-w-4xl mx-auto px-6 py-16">
      <div className="flex justify-between items-start">
        <h1 className="text-3xl font-bold">Organization Dashboard</h1>
        <Link href={`/orgs/${orgId}/security`} className="text-electric text-sm underline">
          Security Operations →
        </Link>
      </div>

      <div className="flex gap-2 mt-6">
        {(["projects", "documents", "api-keys", "webhooks"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-full text-sm border capitalize ${
              tab === t ? "border-electric text-electric" : "border-slate-700 text-slate-400"
            }`}
          >
            {t.replace("-", " ")}
          </button>
        ))}
      </div>

      {error && <p className="text-red-400 mt-4">{error}</p>}

      <div className="mt-8">
        {tab === "projects" && <ProjectsTab orgId={orgId} onError={setError} />}
        {tab === "documents" && <DocumentsTab orgId={orgId} onError={setError} />}
        {tab === "api-keys" && <ApiKeysTab orgId={orgId} onError={setError} />}
        {tab === "webhooks" && <WebhooksTab orgId={orgId} onError={setError} />}
      </div>
    </main>
  );
}

function ProjectsTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [projects, setProjects] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [tasks, setTasks] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [taskTitle, setTaskTitle] = useState("");

  function refresh() {
    listProjects(orgId).then(setProjects).catch((e) => onError(e.message));
  }
  useEffect(refresh, [orgId]);

  useEffect(() => {
    if (selected) listTasks(orgId, selected).then(setTasks).catch(() => setTasks([]));
  }, [selected, orgId]);

  async function handleCreateProject() {
    if (!name.trim()) return;
    try {
      await createProject(orgId, name);
      setName("");
      refresh();
    } catch (e: any) {
      onError(e.message);
    }
  }

  async function handleCreateTask() {
    if (!selected || !taskTitle.trim()) return;
    await createTask(orgId, selected, taskTitle);
    setTaskTitle("");
    listTasks(orgId, selected).then(setTasks);
  }

  const nextStatus: Record<string, string> = { todo: "in_progress", in_progress: "done", done: "todo" };

  async function handleCycleStatus(taskId: string, currentStatus: string) {
    if (!selected) return;
    await updateTaskStatus(orgId, selected, taskId, nextStatus[currentStatus] || "todo");
    listTasks(orgId, selected).then(setTasks);
  }

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Project name"
          className="flex-1 bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
        />
        <button onClick={handleCreateProject} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
          Create
        </button>
      </div>

      <div className="flex gap-2 flex-wrap">
        {projects.map((p: any) => (
          <button
            key={p.id}
            onClick={() => setSelected(p.id)}
            className={`px-3 py-1.5 rounded-full text-sm border ${
              selected === p.id ? "border-electric text-electric" : "border-slate-700 text-slate-400"
            }`}
          >
            {p.name}
          </button>
        ))}
        {projects.length === 0 && <p className="text-slate-500 text-sm">No projects yet.</p>}
      </div>

      {selected && (
        <div className="border-t border-slate-800 pt-6">
          <div className="flex gap-2">
            <input
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              placeholder="New task"
              className="flex-1 bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
            />
            <button onClick={handleCreateTask} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
              Add
            </button>
          </div>
          <div className="space-y-2 mt-4">
            {tasks.map((t: any) => (
              <div key={t.id} className="border border-slate-800 rounded-lg px-4 py-2 text-sm flex justify-between items-center">
                <span className={t.status === "done" ? "line-through text-slate-500" : ""}>{t.title}</span>
                <button
                  onClick={() => handleCycleStatus(t.id, t.status)}
                  className={`text-xs px-2 py-1 rounded-full border ${
                    t.status === "done"
                      ? "border-emerald-700 text-emerald-400"
                      : t.status === "in_progress"
                      ? "border-amber-700 text-amber-400"
                      : "border-slate-700 text-slate-400"
                  }`}
                >
                  {t.status}
                </button>
              </div>
            ))}
            {tasks.length === 0 && <p className="text-slate-500 text-sm">No tasks yet.</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function DocumentsTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [docs, setDocs] = useState<any[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  function refresh() {
    listDocuments(orgId).then(setDocs).catch((e) => onError(e.message));
  }
  useEffect(refresh, [orgId]);

  async function handleUpload() {
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    try {
      await uploadDocument(orgId, file);
      if (fileInput.current) fileInput.current.value = "";
      refresh();
    } catch (e: any) {
      onError(e.message);
    }
  }

  async function handleDownload(id: string) {
    const res = await downloadDocument(orgId, id);
    window.open(res.download_url, "_blank");
  }

  async function handleDelete(id: string) {
    await deleteDocument(orgId, id);
    refresh();
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input ref={fileInput} type="file" className="text-sm text-slate-400" />
        <button onClick={handleUpload} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
          Upload
        </button>
      </div>
      <div className="space-y-2">
        {docs.map((d: any) => (
          <div key={d.id} className="flex justify-between items-center border border-slate-800 rounded-lg px-4 py-3 text-sm">
            <span>{d.filename}</span>
            <span className="text-slate-500">{(d.size_bytes / 1024).toFixed(1)} KB</span>
            <div className="flex gap-3">
              <button onClick={() => handleDownload(d.id)} className="text-electric underline">Download</button>
              <button onClick={() => handleDelete(d.id)} className="text-red-400 underline">Delete</button>
            </div>
          </div>
        ))}
        {docs.length === 0 && <p className="text-slate-500 text-sm">No documents yet.</p>}
      </div>
    </div>
  );
}

function ApiKeysTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [keys, setKeys] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState<string | null>(null);

  function refresh() {
    listApiKeys(orgId).then(setKeys).catch((e) => onError(e.message));
  }
  useEffect(refresh, [orgId]);

  async function handleCreate() {
    if (!name.trim()) return;
    try {
      const res = await createApiKey(orgId, name);
      setNewKey(res.plaintext_key);
      setName("");
      refresh();
    } catch (e: any) {
      onError(e.message);
    }
  }

  async function handleRevoke(id: string) {
    await revokeApiKey(orgId, id);
    refresh();
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Key name"
          className="flex-1 bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
        />
        <button onClick={handleCreate} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
          Generate
        </button>
      </div>
      {newKey && (
        <p className="font-mono text-sm bg-navy/60 border border-amber-800 rounded-lg p-3 text-amber-300">
          {newKey} — shown once, copy it now.
        </p>
      )}
      <div className="space-y-2">
        {keys.map((k: any) => (
          <div key={k.id} className="flex justify-between items-center border border-slate-800 rounded-lg px-4 py-3 text-sm">
            <span>{k.name}</span>
            <span className="text-slate-500">{k.revoked_at ? "revoked" : "active"}</span>
            {!k.revoked_at && (
              <button onClick={() => handleRevoke(k.id)} className="text-red-400 underline">Revoke</button>
            )}
          </div>
        ))}
        {keys.length === 0 && <p className="text-slate-500 text-sm">No API keys yet.</p>}
      </div>
    </div>
  );
}

function WebhooksTab({ orgId, onError }: { orgId: string; onError: (e: string) => void }) {
  const [hooks, setHooks] = useState<any[]>([]);
  const [url, setUrl] = useState("");
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  function refresh() {
    listWebhooks(orgId).then(setHooks).catch((e) => onError(e.message));
  }
  useEffect(refresh, [orgId]);

  async function handleCreate() {
    if (!url.trim()) return;
    try {
      const res = await createWebhook(orgId, url, ["task.created"]);
      setNewSecret(res.signing_secret);
      setUrl("");
      refresh();
    } catch (e: any) {
      onError(e.message);
    }
  }

  async function handleTest(id: string) {
    const res = await testWebhook(orgId, id);
    setTestResult(`${id.slice(0, 8)}: ${res.status}`);
  }

  async function handleDelete(id: string) {
    await deleteWebhook(orgId, id);
    refresh();
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://your-endpoint.example.com/webhook"
          className="flex-1 bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
        />
        <button onClick={handleCreate} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
          Register
        </button>
      </div>
      {newSecret && (
        <p className="font-mono text-sm bg-navy/60 border border-amber-800 rounded-lg p-3 text-amber-300 break-all">
          Signing secret: {newSecret} — shown once, copy it now.
        </p>
      )}
      {testResult && <p className="text-sm text-slate-400">{testResult}</p>}
      <div className="space-y-2">
        {hooks.map((h: any) => (
          <div key={h.id} className="flex justify-between items-center border border-slate-800 rounded-lg px-4 py-3 text-sm">
            <span className="truncate max-w-xs">{h.target_url}</span>
            <span className="text-slate-500">{h.is_active ? "active" : "inactive"}</span>
            <div className="flex gap-3">
              <button onClick={() => handleTest(h.id)} className="text-electric underline">Send test</button>
              <button onClick={() => handleDelete(h.id)} className="text-red-400 underline">Delete</button>
            </div>
          </div>
        ))}
        {hooks.length === 0 && <p className="text-slate-500 text-sm">No webhooks yet.</p>}
      </div>
    </div>
  );
}
