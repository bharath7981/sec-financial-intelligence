import {
  Company,
  Filing,
  QueryResponse,
  SourceCitation,
  IngestionJob,
  EvaluationRun,
  HealthStatus,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE
  ? `${import.meta.env.VITE_API_BASE.replace(/\/$/, '')}/api`
  : '/api';

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function searchCompanies(q: string): Promise<Company[]> {
  const res = await fetch(`${API_BASE}/companies/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) throw new Error('Failed to search companies');
  const data = await res.json();
  return Array.isArray(data) ? data : (data.results || []);
}

export async function getCompany(ticker: string): Promise<Company> {
  const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error(`Company ${ticker} not found`);
  return res.json();
}

export async function getCompanyFilings(
  ticker: string,
  formType?: string,
  fiscalYear?: number
): Promise<{ filings: Filing[]; total: number }> {
  const params = new URLSearchParams();
  if (formType) params.append('form_type', formType);
  if (fiscalYear) params.append('fiscal_year', fiscalYear.toString());
  const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(ticker)}/filings?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch filings');
  return res.json();
}

export async function triggerIngestion(
  ticker: string,
  options: {
    form_types?: string[];
    fiscal_years?: number[];
    max_filings?: number;
  }
): Promise<{ job_id: string; ticker: string; status: string; message: string }> {
  const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(ticker)}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to trigger ingestion');
  }
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<IngestionJob> {
  const res = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`);
  if (!res.ok) throw new Error('Failed to fetch job status');
  return res.json();
}

export async function queryResearch(
  ticker: string,
  question: string,
  options?: {
    retrieval_mode?: string;
    use_reranker?: boolean;
    fiscal_years?: number[];
  }
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ticker,
      question,
      retrieval_mode: options?.retrieval_mode || 'hybrid',
      use_reranker: options?.use_reranker ?? true,
      fiscal_years: options?.fiscal_years,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Query request failed');
  }
  return res.json();
}

export async function getChunkDetail(chunkId: string): Promise<{
  id: string;
  chunk_type: string;
  content: string;
  section: string;
  form_type: string;
  fiscal_year: number;
  accession_number: string;
  source_url: string;
  parent_id?: string;
  parent_content?: string;
}> {
  const res = await fetch(`${API_BASE}/sources/${encodeURIComponent(chunkId)}`);
  if (!res.ok) throw new Error('Failed to fetch source chunk');
  return res.json();
}

export async function getMetrics(ticker: string): Promise<{
  ticker: string;
  facts: any[];
  calculated_metrics: any[];
}> {
  const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(ticker)}/metrics`);
  if (!res.ok) throw new Error('Failed to fetch metrics');
  return res.json();
}

export async function listEvaluations(): Promise<EvaluationRun[]> {
  const res = await fetch(`${API_BASE}/evaluations/`);
  if (!res.ok) throw new Error('Failed to list evaluation runs');
  return res.json();
}

export async function runEvaluation(config: {
  retrieval_mode: string;
  use_reranker: boolean;
}): Promise<EvaluationRun> {
  const res = await fetch(`${API_BASE}/evaluations/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: `Benchmark (${config.retrieval_mode}${config.use_reranker ? '+rerank' : ''})`,
      config,
    }),
  });
  if (!res.ok) throw new Error('Failed to start evaluation run');
  return res.json();
}

export async function getEvaluation(runId: string): Promise<EvaluationRun> {
  const res = await fetch(`${API_BASE}/evaluations/${encodeURIComponent(runId)}`);
  if (!res.ok) throw new Error('Failed to fetch evaluation run');
  return res.json();
}
