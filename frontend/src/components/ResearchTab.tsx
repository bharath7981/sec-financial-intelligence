import React, { useState } from 'react';
import {
  Search,
  Sparkles,
  Calculator,
  ShieldCheck,
  FileSpreadsheet,
  ExternalLink,
  Clock,
  Layers,
  AlertTriangle,
  Copy,
  Check,
} from 'lucide-react';
import { Company, QueryResponse, SourceCitation } from '../types';
import { queryResearch } from '../services/api';

interface ResearchTabProps {
  currentCompany: Company | null;
  onOpenCitation: (citation: SourceCitation) => void;
}

const SAMPLE_PROMPTS = [
  'What was total revenue in fiscal year 2023?',
  'Calculate gross margin and operating margin for 2022 vs 2023',
  'What was Free Cash Flow and how was CapEx treated?',
  'What are the key risk factors regarding supply chain and international concentration?',
  'Compare net income and revenue growth between FY2022 and FY2023',
];

export const ResearchTab: React.FC<ResearchTabProps> = ({
  currentCompany,
  onOpenCitation,
}) => {
  const [question, setQuestion] = useState('');
  const [retrievalMode, setRetrievalMode] = useState('hybrid');
  const [useReranker, setUseReranker] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e?: React.FormEvent, customQ?: string) => {
    if (e) e.preventDefault();
    const queryText = customQ || question;
    if (!queryText.trim() || !currentCompany) return;

    setLoading(true);
    setError(null);

    try {
      const res = await queryResearch(currentCompany.ticker, queryText.trim(), {
        retrieval_mode: retrievalMode,
        use_reranker: useReranker,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Error executing research query');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyAnswer = () => {
    if (result?.answer) {
      navigator.clipboard.writeText(result.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Helper to format large dollar numbers
  const formatMoney = (val: number) => {
    if (Math.abs(val) >= 1_000_000_000) {
      return `$${(val / 1_000_000_000).toFixed(2)}B`;
    }
    if (Math.abs(val) >= 1_000_000) {
      return `$${(val / 1_000_000).toFixed(2)}M`;
    }
    return `$${val.toLocaleString()}`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Search Console Card */}
      <div className="card glow-cyan" style={{ border: '1px solid var(--border-highlight)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={18} color="var(--accent-cyan)" />
            <h2 style={{ fontSize: '16px', fontWeight: 700 }}>Financial Research & Verified RAG</h2>
          </div>

          {/* Retrieval Mode Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <Layers size={14} />
              <span>Strategy:</span>
              <select
                value={retrievalMode}
                onChange={(e) => setRetrievalMode(e.target.value)}
                style={{
                  backgroundColor: 'var(--bg-input)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-primary)',
                  padding: '4px 8px',
                  fontSize: '12px',
                  outline: 'none',
                }}
              >
                <option value="hybrid">Hybrid RRF (Dense + Sparse)</option>
                <option value="dense">Dense Vector Only</option>
                <option value="sparse">Sparse BM25 Only</option>
              </select>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={useReranker}
                onChange={(e) => setUseReranker(e.target.checked)}
                style={{ accentColor: 'var(--accent-cyan)' }}
              />
              Reranker
            </label>
          </div>
        </div>

        {/* Input Form */}
        <form onSubmit={(e) => handleSubmit(e)} style={{ display: 'flex', gap: '10px' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={18} color="var(--text-muted)" style={{ position: 'absolute', left: '14px', top: '13px' }} />
            <input
              type="text"
              placeholder={currentCompany ? `Ask any question about ${currentCompany.ticker}'s 10-K & 10-Q filings...` : "Select a company first..."}
              disabled={!currentCompany || loading}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 14px 12px 42px',
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '14px',
                outline: 'none',
              }}
            />
          </div>
          <button
            type="submit"
            disabled={!currentCompany || !question.trim() || loading}
            className="btn btn-primary"
            style={{ padding: '0 24px', opacity: (!currentCompany || !question.trim() || loading) ? 0.6 : 1 }}
          >
            {loading ? 'Analyzing...' : 'Execute Research'}
          </button>
        </form>

        {/* Prompt Chips */}
        <div style={{ marginTop: '14px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Suggested:</span>
          {SAMPLE_PROMPTS.map((sample, idx) => (
            <button
              key={idx}
              onClick={() => {
                setQuestion(sample);
                handleSubmit(undefined, sample);
              }}
              disabled={!currentCompany || loading}
              style={{
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: 'var(--radius-full)',
                padding: '4px 10px',
                fontSize: '11px',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent-cyan)';
                e.currentTarget.style.color = 'var(--accent-cyan)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.08)';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }}
            >
              {sample}
            </button>
          ))}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="card" style={{ border: '1px solid var(--accent-rose)', backgroundColor: 'rgba(244, 63, 94, 0.08)', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <AlertTriangle color="var(--accent-rose)" size={20} />
          <div>
            <div style={{ fontWeight: 600, color: 'var(--accent-rose)' }}>Query Error</div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{error}</div>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '32px', textAlign: 'center' }}>
          <div style={{ display: 'inline-flex', justifyContent: 'center' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '50%', border: '3px solid rgba(56, 189, 248, 0.2)', borderTopColor: 'var(--accent-cyan)', animation: 'spin 1s linear infinite' }} />
          </div>
          <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 600 }}>Analyzing SEC Filings & Financial Statements...</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Executing deterministic fact matching &bull; Running Python math calculation &bull; Fusing parent-child context
            </p>
          </div>
        </div>
      )}

      {/* Results View */}
      {result && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Main Answer Card */}
          <div className="card" style={{ borderLeft: '4px solid var(--accent-cyan)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldCheck size={18} color="var(--accent-emerald)" />
                <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>Verified Grounded Answer</span>
                <span className="badge badge-cyan">{result.query_type}</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={13} /> {result.execution_time_ms}ms
                </span>
                <button
                  onClick={handleCopyAnswer}
                  className="btn btn-secondary"
                  style={{ padding: '4px 10px', fontSize: '11px' }}
                >
                  {copied ? <Check size={12} color="var(--accent-emerald)" /> : <Copy size={12} />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>

            {/* Answer Content */}
            <div style={{
              fontSize: '14.5px',
              lineHeight: '1.7',
              color: '#e2e8f0',
              whiteSpace: 'pre-wrap',
              marginBottom: '16px',
            }}>
              {result.answer}
            </div>

            {/* Warnings Alert */}
            {result.warnings && result.warnings.length > 0 && (
              <div style={{
                background: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                borderRadius: 'var(--radius-md)',
                padding: '10px 14px',
                fontSize: '12px',
                color: 'var(--accent-amber)',
                marginBottom: '14px',
              }}>
                {result.warnings.map((w, idx) => (
                  <div key={idx}>&bull; {w}</div>
                ))}
              </div>
            )}

            {/* Legal Disclaimer */}
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)', paddingTop: '10px' }}>
              {result.disclaimer}
            </div>
          </div>

          {/* Deterministic Calculations Card */}
          {result.calculation_steps && result.calculation_steps.length > 0 && (
            <div className="card" style={{ border: '1px solid rgba(16, 185, 129, 0.25)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                <Calculator size={18} color="var(--accent-emerald)" />
                <h3 style={{ fontSize: '14px', fontWeight: 700 }}>Python Financial Calculation Audit Trail</h3>
                <span className="badge badge-emerald">Zero-Hallucination Math</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {result.calculation_steps.map((step) => (
                  <div
                    key={step.step}
                    style={{
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-md)',
                      padding: '12px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 600, fontSize: '13px' }}>{step.description}</span>
                      {step.result !== undefined && (
                        <span className="mono badge badge-emerald" style={{ fontSize: '13px' }}>
                          Result: {typeof step.result === 'number' ? (step.result < 1 && step.result > -1 ? `${(step.result * 100).toFixed(2)}%` : step.result.toLocaleString()) : step.result}
                        </span>
                      )}
                    </div>
                    {step.formula && (
                      <div className="mono" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Formula: {step.formula}
                      </div>
                    )}
                    {step.inputs && (
                      <div className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        Inputs: {JSON.stringify(step.inputs)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Structured XBRL Facts Used */}
          {result.facts_used && result.facts_used.length > 0 && (
            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                <FileSpreadsheet size={18} color="var(--accent-cyan)" />
                <h3 style={{ fontSize: '14px', fontWeight: 700 }}>Verified Filing Facts Used</h3>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '8px' }}>Concept</th>
                      <th style={{ padding: '8px' }}>Fiscal Period</th>
                      <th style={{ padding: '8px' }}>Value</th>
                      <th style={{ padding: '8px' }}>Form</th>
                      <th style={{ padding: '8px' }}>Accession</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.facts_used.map((fact, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                        <td style={{ padding: '8px', fontWeight: 600 }}>{fact.concept}</td>
                        <td className="mono" style={{ padding: '8px' }}>FY{fact.fiscal_year} ({fact.fiscal_period})</td>
                        <td className="mono" style={{ padding: '8px', color: 'var(--accent-emerald)', fontWeight: 600 }}>
                          {formatMoney(fact.value)}
                        </td>
                        <td style={{ padding: '8px' }}><span className="badge badge-cyan">{fact.form_type}</span></td>
                        <td className="mono" style={{ padding: '8px', color: 'var(--text-muted)', fontSize: '11px' }}>
                          {fact.accession_number || 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Source Citations Inspector Shelf */}
          {result.citations && result.citations.length > 0 && (
            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ExternalLink size={18} color="var(--accent-violet)" />
                  <h3 style={{ fontSize: '14px', fontWeight: 700 }}>Retrieved Filing Evidence & Citations ({result.citations.length})</h3>
                </div>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Click card to verify exact filing passage</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '12px' }}>
                {result.citations.map((citation) => (
                  <div
                    key={citation.source_id}
                    onClick={() => onOpenCitation(citation)}
                    style={{
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-md)',
                      padding: '12px',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--accent-violet)';
                      e.currentTarget.style.background = 'rgba(168, 85, 247, 0.05)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border-color)';
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)';
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span className="badge badge-violet">{citation.source_id}</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {citation.form_type} &bull; FY{citation.fiscal_year}
                      </span>
                    </div>

                    <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {citation.section || 'SEC Disclosure'}
                    </div>

                    <div style={{
                      fontSize: '11px',
                      color: 'var(--text-secondary)',
                      overflow: 'hidden',
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                      lineHeight: '1.4',
                    }}>
                      "{citation.content_preview}"
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)', borderTop: '1px solid rgba(255, 255, 255, 0.04)', paddingTop: '6px' }}>
                      <span>Score: {citation.relevance_score ? citation.relevance_score.toFixed(3) : 'N/A'}</span>
                      <span style={{ color: 'var(--accent-violet)', display: 'flex', alignItems: 'center', gap: '3px' }}>
                        View in Context <ExternalLink size={10} />
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
