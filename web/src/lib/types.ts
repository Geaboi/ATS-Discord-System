export interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  url: string;
  description: string | null;
  salary_min: number | null;
  salary_max: number | null;
  source: string;
  tags: string[];
  relevance_score: number | null;
  score_reasoning: string | null;
  status: "new" | "bookmarked" | "dismissed";
  posted_at: string | null;
  scraped_at: string;
  experience_level: string | null;
  notified: boolean;
}

export interface JobListResponse {
  items: Job[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export type ApplicationStage =
  | "interested"
  | "applied"
  | "phone_screen"
  | "technical"
  | "onsite"
  | "offer"
  | "rejected"
  | "withdrawn";

export interface Application {
  id: string;
  job_id: string;
  stage: ApplicationStage;
  applied_date: string | null;
  next_action: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationNote {
  id: string;
  application_id: string;
  content: string;
  created_at: string;
}

export interface Resume {
  id: string;
  name: string;
  file_type: string;
  is_master: boolean;
  tailored_for: string | null;
  parent_id: string | null;
  created_at: string;
}

export interface TailorStatus {
  task_id: string;
  status: "pending" | "processing" | "complete" | "error";
  download_url: string | null;
  error: string | null;
}

export interface AppSettings {
  discord_webhook: string | null;
  score_threshold: number;
  scrape_interval: number;
}

export interface HealthStatus {
  db: string;
  ollama: string;
  discord: string;
}

export interface ScrapeRun {
  id: string;
  source: string;
  started_at: string;
  finished_at: string | null;
  jobs_found: number;
  jobs_added: number;
  error: string | null;
}
