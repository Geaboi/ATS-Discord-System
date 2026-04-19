"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AppSettings, HealthStatus, ScrapeRun } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [scrapeStatus, setScrapeStatus] = useState<{ runs: ScrapeRun[]; scraping_now: boolean } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function load() {
    const [s, h, sc] = await Promise.all([
      api.get<AppSettings>("/api/settings"),
      api.get<HealthStatus>("/api/settings/health"),
      api.get<{ runs: ScrapeRun[]; scraping_now: boolean }>("/api/jobs/scrape/status"),
    ]);
    setSettings(s);
    setHealth(h);
    setScrapeStatus(sc);
  }

  useEffect(() => { load(); }, []);

  async function handleSave(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    await api.patch("/api/settings", settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    setSaving(false);
  }

  function StatusDot({ value }: { value: string }) {
    const isOk = value === "ok" || value === "configured";
    return (
      <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${isOk ? "text-emerald-600" : "text-red-500"}`}>
        <span className={`w-2 h-2 rounded-full ${isOk ? "bg-emerald-500" : "bg-red-500"}`} />
        {value}
      </span>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8 space-y-8">
      <h1 className="text-xl font-bold text-slate-900">Settings</h1>

      {/* Health */}
      <section className="bg-white rounded-xl border border-slate-200 p-5">
        <h2 className="font-semibold text-slate-900 mb-4">System Health</h2>
        {health ? (
          <div className="grid grid-cols-3 gap-4">
            {Object.entries(health).map(([key, val]) => (
              <div key={key} className="text-center p-3 bg-slate-50 rounded-lg">
                <p className="text-xs text-slate-500 mb-1 capitalize">{key}</p>
                <StatusDot value={val} />
              </div>
            ))}
          </div>
        ) : (
          <div className="h-16 animate-pulse bg-slate-100 rounded-lg" />
        )}
      </section>

      {/* Configuration */}
      <section className="bg-white rounded-xl border border-slate-200 p-5">
        <h2 className="font-semibold text-slate-900 mb-4">Configuration</h2>
        {settings ? (
          <form onSubmit={handleSave} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Discord Webhook URL
              </label>
              <input
                type="url"
                value={settings.discord_webhook || ""}
                onChange={(e) => setSettings({ ...settings, discord_webhook: e.target.value || null })}
                placeholder="https://discord.com/api/webhooks/..."
                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              <p className="text-xs text-slate-400 mt-1">Alerts will be sent here when new relevant jobs are found</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Minimum Relevance Score
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={Math.round(settings.score_threshold * 100)}
                  onChange={(e) => setSettings({ ...settings, score_threshold: Number(e.target.value) / 100 })}
                  className="flex-1"
                />
                <span className="text-sm font-medium text-slate-700 w-10 text-right">
                  {Math.round(settings.score_threshold * 100)}%
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Only jobs above this score trigger Discord alerts
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Scrape Interval (minutes)
              </label>
              <input
                type="number"
                min={15}
                max={1440}
                value={settings.scrape_interval}
                onChange={(e) => setSettings({ ...settings, scrape_interval: Number(e.target.value) })}
                className="w-32 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>

            <button
              type="submit"
              disabled={saving}
              className="text-sm font-medium bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary/90 disabled:opacity-60 transition-all"
            >
              {saved ? "✓ Saved" : saving ? "Saving…" : "Save Settings"}
            </button>
          </form>
        ) : (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 animate-pulse bg-slate-100 rounded-lg" />
            ))}
          </div>
        )}
      </section>

      {/* Scrape history */}
      <section className="bg-white rounded-xl border border-slate-200 p-5">
        <h2 className="font-semibold text-slate-900 mb-4">Recent Scrape Runs</h2>
        {scrapeStatus ? (
          scrapeStatus.runs.length === 0 ? (
            <p className="text-sm text-slate-400">No scrape runs yet. Click &ldquo;Scrape Now&rdquo; on the Job Feed.</p>
          ) : (
            <div className="space-y-2">
              {scrapeStatus.runs.slice(0, 10).map((run) => (
                <div key={run.id} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                  <div>
                    <span className="text-sm font-medium text-slate-700 capitalize">
                      {run.source.replace("_", " ")}
                    </span>
                    {run.error && (
                      <span className="ml-2 text-xs text-red-500">{run.error.slice(0, 60)}</span>
                    )}
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-slate-500">
                      +{run.jobs_added} new of {run.jobs_found} found
                    </p>
                    <p className="text-xs text-slate-400">{timeAgo(run.started_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          <div className="h-32 animate-pulse bg-slate-100 rounded-lg" />
        )}
      </section>
    </div>
  );
}
