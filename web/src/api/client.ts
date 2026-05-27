import axios from 'axios';

const API_BASE = (import.meta as any).env?.VITE_API_BASE?.toString().trim() || '';

const client = axios.create({
  baseURL: API_BASE ? `${API_BASE.replace(/\/+$/, '')}` : '',
  timeout: 60_000,
  withCredentials: false,
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      console.warn('API auth required (401). Check basic-auth credentials.');
    }
    return Promise.reject(err);
  },
);

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Gosb {
  id: number;
  name: string;
  chat_id: string;
  thread_id: string | null;
  region: string;
  keywords: string[] | string | null;
  active: number;
  created_at: string;
  system_prompt?: string | null;
}

export interface NewsClassification {
  news_id: number;
  gosb_id: number;
  mode: string;
  relevant: number;
  category: string | null;
  impact: string | null;
  confidence: number | null;
  summary: string | null;
  reject_reason: string | null;
  created_at: string;
}

export interface SentNewsLink {
  news_id: number;
  gosb_id: number;
  summary: string | null;
  run_id: string | null;
  sent_at: string;
}

export interface FeedbackItem {
  id?: number;
  news_id: number;
  gosb_id: number | null;
  user_id: string | null;
  username: string | null;
  action: string;
  comment: string | null;
  created_at: string;
  news_title?: string;
  news_url?: string;
  gosb_name?: string;
}

export interface NewsItem {
  id: number;
  url: string;
  title: string;
  body: string | null;
  source: string | null;
  published_at: string | null;
  collected_at: string;
  classifications?: NewsClassification[];
  sent_to?: SentNewsLink[];
  feedback?: FeedbackItem[];
}

export interface InsightItem {
  id: number;
  gosb_id: number;
  gosb_name?: string | null;
  gosb_region?: string | null;
  run_id: string | null;
  title: string;
  insight_type: string;
  priority: 'high' | 'medium' | 'low' | string;
  confidence: number;
  why_it_matters: string | null;
  suggested_action: string | null;
  owner_hint: string | null;
  evidence: string | null;
  status: string;
  created_at: string;
  news_links: { news_id: number; title: string; url: string; source?: string; dt?: string }[];
  metric_links: { metric_key: string; metric_name?: string; impact?: string; confidence?: number; reason?: string }[];
  feedback: FeedbackItem[];
  source?: unknown;
}

export interface KnowledgeItem {
  id: number;
  kind: string;
  file_name: string | null;
  source_type: string;
  source_key: string | null;
  preview: string;
  content_length: number;
  revision: number;
  created_at: string;
  username?: string | null;
  thread_id?: string | null;
}

export interface StatsSummary {
  since_hours: number;
  totals: Record<string, number>;
  recent: Record<string, number>;
  insight_priority_breakdown: { priority: string; n: number }[];
  feedback_breakdown: { action: string; n: number }[];
  latest_runs: { run_id: string; started_at: string; finished_at: string; gosbs: number; messages: number }[];
  news_timeline: { day: string; n: number }[];
}

export interface FeedbackCounts {
  useful: number;
  boring: number;
  comments: number;
}

export interface FeedbackResult {
  status: 'inserted' | 'updated' | 'removed';
  action: string;
}

export interface KnowledgeUploadResult {
  status: 'inserted' | 'updated' | 'duplicate';
  id?: number;
}

export interface ChatResponse {
  response: string;
  duration_seconds: number;
}

export const api = {
  health: () => client.get('/health').then((r) => r.data),

  stats: (sinceHours = 168) =>
    client.get<StatsSummary>('/api/v1/stats/summary', { params: { since_hours: sinceHours } }).then((r) => r.data),

  listGosbs: (activeOnly = false) =>
    client.get<{ items: Gosb[] }>('/api/v1/gosbs', { params: { active_only: activeOnly } }).then((r) => r.data),

  listNews: (params: {
    gosb_id?: number;
    only_relevant?: boolean;
    since_hours?: number;
    search?: string;
    limit?: number;
    offset?: number;
  } = {}) => client.get<Page<NewsItem>>('/api/v1/news', { params }).then((r) => r.data),

  getNews: (id: number) => client.get<NewsItem>(`/api/v1/news/${id}`).then((r) => r.data),

  listInsights: (params: {
    gosb_id?: number;
    priority?: string;
    insight_type?: string;
    status?: string;
    limit?: number;
    offset?: number;
  } = {}) => client.get<Page<InsightItem>>('/api/v1/insights', { params }).then((r) => r.data),

  listFeedback: (params: { gosb_id?: number; action?: string; limit?: number; offset?: number } = {}) =>
    client.get<Page<FeedbackItem>>('/api/v1/feedback', { params }).then((r) => r.data),

  listKnowledge: (params: { kind?: string; limit?: number; offset?: number } = {}) =>
    client.get<Page<KnowledgeItem>>('/api/v1/knowledge', { params }).then((r) => r.data),

  // --- Write operations ---

  submitFeedback: (newsId: number, action: string, comment?: string) =>
    client.post<FeedbackResult>(`/api/v1/feedback/news/${newsId}`, { action, comment }).then((r) => r.data),

  submitInsightFeedback: (insightId: number, action: string, comment?: string) =>
    client.post<FeedbackResult>(`/api/v1/feedback/insights/${insightId}`, { action, comment }).then((r) => r.data),

  getFeedbackCounts: (newsId: number) =>
    client.get<FeedbackCounts>(`/api/v1/feedback/news/${newsId}/counts`).then((r) => r.data),

  getInsightFeedbackCounts: (insightId: number) =>
    client.get<FeedbackCounts>(`/api/v1/feedback/insights/${insightId}/counts`).then((r) => r.data),

  uploadKnowledge: (kind: string, file?: File, text?: string) => {
    const form = new FormData();
    form.append('kind', kind);
    if (file) form.append('file', file);
    if (text) form.append('text', text);
    return client.post<KnowledgeUploadResult>('/api/v1/knowledge/upload', form).then((r) => r.data);
  },

  sendChat: (message: string) =>
    client.post<ChatResponse>('/api/v1/chat', { message }, { timeout: 300_000 }).then((r) => r.data),
};

export default client;
