export interface Company {
  id: string;
  ticker: string;
  cik: string;
  name: string;
  sic?: string;
  sic_description?: string;
  filing_count?: number;
  latest_filing_date?: string;
}

export interface Filing {
  id: string;
  accession_number: string;
  form_type: string;
  filing_date: string;
  report_date?: string;
  fiscal_year?: number;
  fiscal_period?: string;
  is_processed: boolean;
  chunk_count: number;
  sec_filing_url?: string;
}

export interface SourceCitation {
  source_id: string;
  chunk_id: string;
  content_preview: string;
  section?: string;
  form_type?: string;
  fiscal_year?: number;
  fiscal_period?: string;
  filing_date?: string;
  accession_number?: string;
  source_url?: string;
  relevance_score?: number;
}

export interface CalculationStep {
  step: number;
  description: string;
  formula?: string;
  inputs?: Record<string, any>;
  result?: any;
}

export interface FactUsed {
  fact_id?: string;
  concept: string;
  value: number;
  unit: string;
  fiscal_year: number;
  fiscal_period: string;
  form_type: string;
  filing_date?: string;
  accession_number?: string;
}

export interface QueryResponse {
  answer: string;
  query_type: string;
  citations: SourceCitation[];
  calculation_steps: CalculationStep[];
  facts_used: FactUsed[];
  warnings: string[];
  fiscal_years_covered: number[];
  disclaimer: string;
  execution_time_ms: number;
}

export interface FinancialMetric {
  metric: string;
  display_name: string;
  values: Record<number, number>;
  unit: string;
  category: 'income' | 'balance_sheet' | 'cash_flow' | 'ratio';
}

export interface IngestionJob {
  id: string;
  ticker: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  total_filings: number;
  completed_filings: number;
  failed_filings: number;
  error?: string;
  started_at?: string;
  completed_at?: string;
}

export interface EvaluationRun {
  id: string;
  name: string;
  status: string;
  config: {
    retrieval_mode: string;
    use_reranker: boolean;
  };
  total_questions: number;
  completed_questions: number;
  results_summary?: {
    strategy: {
      retrieval_mode: string;
      use_reranker: boolean;
    };
    accuracy: number;
    citation_coverage: number;
    avg_latency_ms: number;
    total_evaluated: number;
    passed_count: number;
    details: Array<{
      id: string;
      question: string;
      category: string;
      passed: boolean;
      latency_ms?: number;
      citations_count?: number;
      error?: string;
    }>;
  };
  created_at: string;
}

export interface HealthStatus {
  status: string;
  services: {
    database: string;
    qdrant?: string;
  };
  limited_mode: boolean;
  ai_chat_provider: string;
  ai_embedding_provider: string;
  gemini_available: boolean;
  openai_available: boolean;
}
