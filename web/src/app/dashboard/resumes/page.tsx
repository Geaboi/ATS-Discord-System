"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Resume, TailorStatus, Job, JobListResponse, ResumeAnalysis } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

function TailorModal({
  resume,
  onClose,
}: {
  resume: Resume;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<TailorStatus | null>(null);

  async function searchJobs(q: string) {
    const res = await api.get<JobListResponse>(
      `/api/jobs?q=${encodeURIComponent(q)}&limit=10`
    );
    setJobs(res.items);
  }

  async function startTailor() {
    if (!selectedJob) return;
    const res = await api.post<TailorStatus>(`/api/resumes/${resume.id}/tailor`, {
      job_id: selectedJob.id,
    });
    setTaskId(res.task_id);
    setStatus(res);

    // Poll for completion
    const interval = setInterval(async () => {
      const s = await api.get<TailorStatus>(`/api/resumes/tailor/${res.task_id}`);
      setStatus(s);
      if (s.status === "complete" || s.status === "error") {
        clearInterval(interval);
      }
    }, 3000);
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
        <div className="p-6 border-b border-slate-100">
          <h2 className="font-bold text-slate-900">Tailor Resume</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Using: <span className="font-medium">{resume.name}</span>
          </p>
        </div>

        <div className="p-6 space-y-4">
          {/* Job search */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Search for a job to tailor to
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. Google software engineer"
                className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              <button
                onClick={() => searchJobs(query)}
                className="text-sm font-medium bg-slate-100 text-slate-700 px-3 py-2 rounded-lg hover:bg-slate-200 transition-colors"
              >
                Search
              </button>
            </div>
          </div>

          {/* Job results */}
          {jobs.length > 0 && (
            <div className="border border-slate-200 rounded-lg overflow-hidden max-h-48 overflow-y-auto">
              {jobs.map((job) => (
                <button
                  key={job.id}
                  onClick={() => setSelectedJob(job)}
                  className={`w-full text-left px-3 py-2.5 hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0 ${
                    selectedJob?.id === job.id ? "bg-primary/5" : ""
                  }`}
                >
                  <p className="text-sm font-medium text-slate-900">{job.title}</p>
                  <p className="text-xs text-slate-500">{job.company}</p>
                </button>
              ))}
            </div>
          )}

          {selectedJob && (
            <div className="bg-primary/5 rounded-lg px-3 py-2 text-sm">
              <span className="text-slate-600">Selected: </span>
              <span className="font-medium text-primary">{selectedJob.title}</span>
              <span className="text-slate-500"> at {selectedJob.company}</span>
            </div>
          )}

          {/* Status */}
          {status && (
            <div className={`rounded-lg px-3 py-2.5 text-sm ${
              status.status === "complete"
                ? "bg-emerald-50 text-emerald-700"
                : status.status === "error"
                ? "bg-red-50 text-red-700"
                : "bg-blue-50 text-blue-700"
            }`}>
              {status.status === "pending" && "Queued for tailoring…"}
              {status.status === "processing" && (
                <div className="flex items-center gap-2">
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  LLM is tailoring your resume… (~30-60s)
                </div>
              )}
              {status.status === "complete" && (
                <div>
                  ✓ Done!{" "}
                  <a
                    href={status.download_url || "#"}
                    download
                    className="underline font-medium"
                  >
                    Download tailored resume
                  </a>
                </div>
              )}
              {status.status === "error" && `Error: ${status.error}`}
            </div>
          )}
        </div>

        <div className="p-6 pt-0 flex gap-3">
          {!taskId && (
            <button
              onClick={startTailor}
              disabled={!selectedJob}
              className="flex-1 text-sm font-medium bg-primary text-white py-2 rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              Tailor with Ollama
            </button>
          )}
          <button
            onClick={onClose}
            className="flex-1 text-sm font-medium text-slate-600 border border-slate-200 py-2 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [tailoring, setTailoring] = useState<Resume | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Record<string, ResumeAnalysis>>({});
  const [analysisLoading, setAnalysisLoading] = useState<string | null>(null);

  async function load() {
    const data = await api.get<Resume[]>("/api/resumes");
    setResumes(data);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await api.upload<Resume>("/api/resumes/upload", form);
      await load();
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this resume?")) return;
    await api.delete(`/api/resumes/${id}`);
    setResumes((prev) => prev.filter((r) => r.id !== id));
  }

  async function handleAnalyze(id: string) {
    if (analyzing === id) {
      setAnalyzing(null);
      return;
    }
    setAnalyzing(id);
    if (!analysis[id]) {
      setAnalysisLoading(id);
      try {
        const data = await api.get<ResumeAnalysis>(`/api/resumes/${id}/analysis`);
        setAnalysis((prev) => ({ ...prev, [id]: data }));
      } finally {
        setAnalysisLoading(null);
      }
    }
  }

  const masters = resumes.filter((r) => r.is_master);
  const tailored = resumes.filter((r) => !r.is_master);

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-900">Resumes</h1>
        <label className={`cursor-pointer text-sm font-medium bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary/90 transition-colors flex items-center gap-2 ${uploading ? "opacity-60" : ""}`}>
          {uploading ? "Uploading…" : "Upload Resume"}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx"
            onChange={handleUpload}
            className="hidden"
            disabled={uploading}
          />
        </label>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-white rounded-xl border border-slate-200 animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {/* Master resumes */}
          <section className="mb-6">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
              Master Resumes
            </h2>
            {masters.length === 0 ? (
              <div className="bg-white rounded-xl border border-dashed border-slate-200 p-8 text-center text-slate-400">
                <p>No master resume uploaded yet</p>
                <p className="text-sm mt-1">Upload a PDF or DOCX to get started</p>
              </div>
            ) : (
              <div className="space-y-2">
                {masters.map((r) => (
                  <div key={r.id}>
                    <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center justify-between">
                      <div>
                        <p className="font-medium text-sm text-slate-900">{r.name}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{r.file_type.toUpperCase()} · {timeAgo(r.created_at)}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleAnalyze(r.id)}
                          className={`text-xs font-medium transition-colors ${
                            analyzing === r.id ? "text-primary" : "text-slate-500 hover:text-slate-700"
                          }`}
                        >
                          {analyzing === r.id ? "Hide Analysis" : "Analysis"}
                        </button>
                        <button
                          onClick={() => setTailoring(r)}
                          className="text-xs font-medium text-primary hover:text-primary/80 transition-colors"
                        >
                          Tailor →
                        </button>
                        <a
                          href={`/api/resumes/${r.id}/download`}
                          download
                          className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
                        >
                          Download
                        </a>
                        <button
                          onClick={() => handleDelete(r.id)}
                          className="text-xs text-red-400 hover:text-red-600 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                    {analyzing === r.id && (
                      <div className="border border-t-0 border-slate-200 rounded-b-xl bg-slate-50 px-4 py-4">
                        {analysisLoading === r.id ? (
                          <p className="text-sm text-slate-400">Loading analysis…</p>
                        ) : analysis[r.id]?.strengths.length === 0 && analysis[r.id]?.weaknesses.length === 0 ? (
                          <p className="text-sm text-slate-400">No analysis yet — scrape some jobs first.</p>
                        ) : (
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wide mb-2">Strengths</p>
                              <ul className="space-y-1">
                                {analysis[r.id]?.strengths.map((s, i) => (
                                  <li key={i} className="text-xs text-slate-700 flex gap-1.5">
                                    <span className="text-emerald-500 shrink-0">✓</span>{s}
                                  </li>
                                ))}
                              </ul>
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-2">Weaknesses</p>
                              <ul className="space-y-1">
                                {analysis[r.id]?.weaknesses.map((w, i) => (
                                  <li key={i} className="text-xs text-slate-700 flex gap-1.5">
                                    <span className="text-red-400 shrink-0">✗</span>{w}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Tailored versions */}
          <section>
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
              Tailored Versions ({tailored.length})
            </h2>
            {tailored.length === 0 ? (
              <p className="text-sm text-slate-400">
                No tailored versions yet. Upload a master resume and click &ldquo;Tailor&rdquo;.
              </p>
            ) : (
              <div className="space-y-2">
                {tailored.map((r) => (
                  <div key={r.id} className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-sm text-slate-900">{r.name}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{timeAgo(r.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <a
                        href={`/api/resumes/${r.id}/download`}
                        download
                        className="text-xs font-medium text-primary hover:text-primary/80 transition-colors"
                      >
                        Download
                      </a>
                      <button
                        onClick={() => handleDelete(r.id)}
                        className="text-xs text-red-400 hover:text-red-600 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {tailoring && (
        <TailorModal resume={tailoring} onClose={() => { setTailoring(null); load(); }} />
      )}
    </div>
  );
}
