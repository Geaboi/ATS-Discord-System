"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { Job, JobListResponse } from "@/lib/types";
import { formatSalary, timeAgo } from "@/lib/utils";

const SOURCES: Record<string, string> = {
  adzuna: "Adzuna",
  simplify: "SimplifyJobs",
  linkedin_rss: "LinkedIn",
  indeed_rss: "Indeed",
};

function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-slate-400">—</span>;
  const pct = Math.round(score * 100);
  const color =
    score >= 0.85 ? "bg-emerald-500" : score >= 0.70 ? "bg-amber-400" : "bg-orange-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-500">{pct}%</span>
    </div>
  );
}

const LEVEL_STYLES: Record<string, string> = {
  intern: "bg-purple-50 text-purple-600",
  entry: "bg-blue-50 text-blue-600",
  mid: "bg-amber-50 text-amber-600",
  senior: "bg-red-50 text-red-600",
};

function ExperienceBadge({ level }: { level: string | null }) {
  if (!level || level === "unknown" || !LEVEL_STYLES[level]) return null;
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${LEVEL_STYLES[level]}`}>
      {level.charAt(0).toUpperCase() + level.slice(1)}
    </span>
  );
}

function JobCard({ job, onApply }: { job: Job; onApply: (jobId: string) => void }) {
  const [dismissed, setDismissed] = useState(job.status === "dismissed");
  const [bookmarked, setBookmarked] = useState(job.status === "bookmarked");

  async function toggleBookmark() {
    const newStatus = bookmarked ? "new" : "bookmarked";
    await api.patch(`/api/jobs/${job.id}`, { status: newStatus });
    setBookmarked(!bookmarked);
  }

  async function dismiss() {
    await api.patch(`/api/jobs/${job.id}`, { status: "dismissed" });
    setDismissed(true);
  }

  if (dismissed) return null;

  const salary = formatSalary(job.salary_min, job.salary_max);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 hover:border-slate-300 hover:shadow-sm transition-all">
      <div className="flex items-start justify-between gap-3">
        {/* Main info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wide">
              {SOURCES[job.source] || job.source}
            </span>
            {job.remote && (
              <span className="text-xs bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded font-medium">
                Remote
              </span>
            )}
            <ExperienceBadge level={job.experience_level} />
          </div>
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold text-slate-900 hover:text-primary transition-colors text-base leading-tight block truncate"
          >
            {job.title}
          </a>
          <div className="flex items-center gap-2 mt-1 text-sm text-slate-500">
            <span className="font-medium text-slate-700">{job.company}</span>
            {job.location && (
              <>
                <span className="text-slate-300">·</span>
                <span>{job.location}</span>
              </>
            )}
            {salary && (
              <>
                <span className="text-slate-300">·</span>
                <span className="text-emerald-600 font-medium">{salary}</span>
              </>
            )}
            {job.posted_at && (
              <>
                <span className="text-slate-300">·</span>
                <span>{timeAgo(job.posted_at)}</span>
              </>
            )}
          </div>
        </div>

        {/* Score */}
        <div className="shrink-0 flex flex-col items-end gap-1">
          <ScoreBar score={job.relevance_score} />
          <span className="text-xs text-slate-400">{timeAgo(job.scraped_at)}</span>
        </div>
      </div>

      {/* Tags */}
      {job.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {job.tags.slice(0, 6).map((tag) => (
            <span
              key={tag}
              className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Reasoning */}
      {job.score_reasoning && (
        <p className="text-xs text-slate-400 mt-2 line-clamp-2">{job.score_reasoning}</p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-slate-100">
        <button
          onClick={() => onApply(job.id)}
          className="text-xs font-medium bg-primary text-white px-3 py-1.5 rounded-lg hover:bg-primary/90 transition-colors"
        >
          Track Application
        </button>
        <button
          onClick={toggleBookmark}
          className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
            bookmarked
              ? "bg-amber-100 text-amber-700 hover:bg-amber-200"
              : "text-slate-500 hover:bg-slate-100"
          }`}
        >
          {bookmarked ? "Bookmarked" : "Bookmark"}
        </button>
        <button
          onClick={dismiss}
          className="text-xs text-slate-400 hover:text-red-500 ml-auto transition-colors"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<JobListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [filter, setFilter] = useState<"new" | "bookmarked">("new");
  const [minScore, setMinScore] = useState<number>(0);
  const [expLevel, setExpLevel] = useState<string>("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        limit: "20",
        status: filter,
      });
      if (minScore > 0) params.set("min_score", String(minScore / 100));
      if (expLevel) params.set("experience_level", expLevel);
      const res = await api.get<JobListResponse>(`/api/jobs?${params}`);
      setData(res);
    } finally {
      setLoading(false);
    }
  }, [page, filter, minScore, expLevel]);

  useEffect(() => { load(); }, [load]);

  async function handleScrape() {
    setScraping(true);
    await api.post("/api/jobs/scrape");
    setTimeout(() => {
      setScraping(false);
      setPage(1);
      load();
    }, 3000);
  }

  async function handleApply(jobId: string) {
    try {
      await api.post("/api/applications", { job_id: jobId, stage: "interested" });
      alert("Added to your pipeline as Interested!");
    } catch {
      alert("Already in your pipeline.");
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Job Feed</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {data ? `${data.total} jobs found` : "Loading…"}
          </p>
        </div>
        <button
          onClick={handleScrape}
          disabled={scraping}
          className="text-sm font-medium bg-slate-900 text-white px-4 py-2 rounded-lg hover:bg-slate-800 disabled:opacity-60 transition-all flex items-center gap-2"
        >
          {scraping ? (
            <>
              <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Scraping…
            </>
          ) : (
            "Scrape Now"
          )}
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-5">
        <div className="flex rounded-lg border border-slate-200 overflow-hidden text-sm">
          {(["new", "bookmarked"] as const).map((f) => (
            <button
              key={f}
              onClick={() => { setFilter(f); setPage(1); }}
              className={`px-4 py-1.5 font-medium transition-colors ${
                filter === f ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {f === "new" ? "New" : "Bookmarked"}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <span>Min score:</span>
          <select
            value={minScore}
            onChange={(e) => { setMinScore(Number(e.target.value)); setPage(1); }}
            className="border border-slate-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none"
          >
            <option value={0}>Any</option>
            <option value={60}>60%+</option>
            <option value={70}>70%+</option>
            <option value={80}>80%+</option>
          </select>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <span>Level:</span>
          <select
            value={expLevel}
            onChange={(e) => { setExpLevel(e.target.value); setPage(1); }}
            className="border border-slate-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none"
          >
            <option value="">Any</option>
            <option value="intern">Intern</option>
            <option value="entry">Entry</option>
            <option value="mid">Mid</option>
            <option value="senior">Senior</option>
          </select>
        </div>
      </div>

      {/* Job list */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-40 bg-white rounded-xl border border-slate-200 animate-pulse" />
          ))}
        </div>
      ) : data?.items.length === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <p className="text-lg">No jobs found</p>
          <p className="text-sm mt-1">Try clicking &ldquo;Scrape Now&rdquo; to fetch the latest listings</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data?.items.map((job) => (
            <JobCard key={job.id} job={job} onApply={handleApply} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-8">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 text-sm font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40 transition-colors"
          >
            Previous
          </button>
          <span className="text-sm text-slate-500">
            {page} / {data.pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
            disabled={page === data.pages}
            className="px-4 py-2 text-sm font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
