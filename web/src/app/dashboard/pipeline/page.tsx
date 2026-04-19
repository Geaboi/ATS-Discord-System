"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Application, ApplicationStage, Job } from "@/lib/types";
import { STAGE_LABELS, STAGE_COLORS, timeAgo } from "@/lib/utils";

const STAGE_ORDER: ApplicationStage[] = [
  "interested",
  "applied",
  "phone_screen",
  "technical",
  "onsite",
  "offer",
  "rejected",
  "withdrawn",
];

const STAGE_HEADER_COLORS: Record<string, string> = {
  interested: "bg-slate-100 text-slate-700 border-slate-200",
  applied: "bg-blue-100 text-blue-700 border-blue-200",
  phone_screen: "bg-yellow-100 text-yellow-700 border-yellow-200",
  technical: "bg-orange-100 text-orange-700 border-orange-200",
  onsite: "bg-purple-100 text-purple-700 border-purple-200",
  offer: "bg-emerald-100 text-emerald-700 border-emerald-200",
  rejected: "bg-red-100 text-red-700 border-red-200",
  withdrawn: "bg-gray-100 text-gray-500 border-gray-200",
};

interface AppWithJob extends Application {
  job?: Job;
}

function ApplicationCard({
  app,
  onStageChange,
}: {
  app: AppWithJob;
  onStageChange: (id: string, stage: ApplicationStage) => void;
}) {
  const [editing, setEditing] = useState(false);

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3 shadow-sm">
      <p className="font-medium text-sm text-slate-900 line-clamp-2">
        {app.job?.title || "Unknown Role"}
      </p>
      <p className="text-xs text-slate-500 mt-0.5">{app.job?.company || "—"}</p>
      <p className="text-xs text-slate-400 mt-2">{timeAgo(app.updated_at)}</p>

      {editing ? (
        <div className="mt-2">
          <select
            defaultValue={app.stage}
            onChange={(e) => {
              onStageChange(app.id, e.target.value as ApplicationStage);
              setEditing(false);
            }}
            autoFocus
            onBlur={() => setEditing(false)}
            className="w-full text-xs border border-slate-200 rounded-md px-2 py-1 focus:outline-none"
          >
            {STAGE_ORDER.map((s) => (
              <option key={s} value={s}>{STAGE_LABELS[s]}</option>
            ))}
          </select>
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="mt-2 text-xs text-slate-400 hover:text-primary transition-colors"
        >
          Move stage →
        </button>
      )}
    </div>
  );
}

function KanbanColumn({
  stage,
  apps,
  onStageChange,
}: {
  stage: ApplicationStage;
  apps: AppWithJob[];
  onStageChange: (id: string, stage: ApplicationStage) => void;
}) {
  return (
    <div className="flex-shrink-0 w-56">
      <div className={`flex items-center justify-between px-3 py-2 rounded-t-lg border ${STAGE_HEADER_COLORS[stage]}`}>
        <span className="text-xs font-semibold uppercase tracking-wide">
          {STAGE_LABELS[stage]}
        </span>
        <span className="text-xs font-bold opacity-60">{apps.length}</span>
      </div>
      <div className="bg-slate-50 rounded-b-lg border-x border-b border-slate-200 p-2 min-h-[200px] space-y-2">
        {apps.map((app) => (
          <ApplicationCard key={app.id} app={app} onStageChange={onStageChange} />
        ))}
        {apps.length === 0 && (
          <p className="text-xs text-slate-300 text-center pt-8">Empty</p>
        )}
      </div>
    </div>
  );
}

export default function PipelinePage() {
  const [applications, setApplications] = useState<AppWithJob[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const apps = await api.get<Application[]>("/api/applications");
      // Fetch job info for each application
      const withJobs: AppWithJob[] = await Promise.all(
        apps.map(async (a) => {
          try {
            const job = await api.get<Job>(`/api/jobs/${a.job_id}`);
            return { ...a, job };
          } catch {
            return a;
          }
        })
      );
      setApplications(withJobs);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleStageChange(id: string, stage: ApplicationStage) {
    await api.patch(`/api/applications/${id}`, { stage });
    setApplications((prev) =>
      prev.map((a) => (a.id === id ? { ...a, stage } : a))
    );
  }

  const byStage = STAGE_ORDER.reduce<Record<string, AppWithJob[]>>((acc, s) => {
    acc[s] = applications.filter((a) => a.stage === s);
    return acc;
  }, {} as Record<string, AppWithJob[]>);

  const total = applications.length;
  const active = applications.filter(
    (a) => !["rejected", "withdrawn"].includes(a.stage)
  ).length;

  if (loading) {
    return (
      <div className="p-8">
        <div className="h-8 w-48 bg-slate-200 rounded animate-pulse mb-6" />
        <div className="flex gap-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="w-56 h-64 bg-slate-200 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Pipeline</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {total} total · {active} active
          </p>
        </div>
      </div>

      {total === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <p className="text-lg">No applications yet</p>
          <p className="text-sm mt-1">
            Go to Job Feed and click &ldquo;Track Application&rdquo; on a job
          </p>
        </div>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {STAGE_ORDER.map((stage) => (
            <KanbanColumn
              key={stage}
              stage={stage}
              apps={byStage[stage] || []}
              onStageChange={handleStageChange}
            />
          ))}
        </div>
      )}
    </div>
  );
}
