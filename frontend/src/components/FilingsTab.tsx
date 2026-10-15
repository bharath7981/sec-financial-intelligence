import React, { useEffect, useState } from 'react';
import { FileText, DownloadCloud, CheckCircle2, Clock, AlertCircle, ExternalLink, RefreshCw } from 'lucide-react';
import { Company, Filing, IngestionJob } from '../types';
import { getCompanyFilings, triggerIngestion, getJobStatus } from '../services/api';

interface FilingsTabProps {
  currentCompany: Company | null;
  onRefreshCompany: () => void;
}

export const FilingsTab: React.FC<FilingsTabProps> = ({ currentCompany, onRefreshCompany }) => {
  const [filings, setFilings] = useState<Filing[]>([]);
  const [loading, setLoading] = useState(false);
  const [formFilter, setFormFilter] = useState<string>('');
  const [activeJob, setActiveJob] = useState<IngestionJob | null>(null);
  const [ingestLoading, setIngestLoading] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);

  // Ingestion config state
  const [include10K, setInclude10K] = useState(true);
  const [include10Q, setInclude10Q] = useState(true);
  const [maxFilings, setMaxFilings] = useState(5);

  const fetchFilings = async () => {
    if (!currentCompany) return;
    setLoading(true);
    try {
      const res = await getCompanyFilings(currentCompany.ticker, formFilter || undefined);
      setFilings(res.filings);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFilings();
  }, [currentCompany?.ticker, formFilter]);

  // Polling active ingestion job
  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed') return;

    const interval = setInterval(async () => {
      try {
        const job = await getJobStatus(activeJob.id);
        setActiveJob(job);
        if (job.status === 'completed') {
          fetchFilings();
          onRefreshCompany();
        }
      } catch (err) {
        console.error('Job polling error:', err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [activeJob?.id, activeJob?.status]);

  const handleStartIngest = async () => {
    if (!currentCompany) return;
    setIngestLoading(true);
    setIngestError(null);

    const forms = [];
    if (include10K) forms.push('10-K');
    if (include10Q) forms.push('10-Q');

    try {
      const res = await triggerIngestion(currentCompany.ticker, {
        form_types: forms,
        max_filings: maxFilings,
      });
      setActiveJob({
        id: res.job_id,
        ticker: res.ticker,
        status: 'pending',
        progress: 0,
        total_filings: 0,
        completed_filings: 0,
        failed_filings: 0,
      });
    } catch (err: any) {
      setIngestError(err.message || 'Failed to start ingestion');
    } finally {
      setIngestLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Ingestion Trigger Panel */}
      <div className="card" style={{ border: '1px solid var(--border-highlight)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <DownloadCloud size={18} color="var(--accent-cyan)" />
              SEC EDGAR Filing Ingestion Service
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Discovers filings from SEC submissions API, parses HTML, extracts tables, and indexes chunks.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={include10K}
                onChange={(e) => setInclude10K(e.target.checked)}
                style={{ accentColor: 'var(--accent-cyan)' }}
              />
              Include 10-K (Annual)
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={include10Q}
                onChange={(e) => setInclude10Q(e.target.checked)}
                style={{ accentColor: 'var(--accent-cyan)' }}
              />
              Include 10-Q (Quarterly)
            </label>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>
            <span>Max Filings:</span>
            <select
              value={maxFilings}
              onChange={(e) => setMaxFilings(Number(e.target.value))}
              style={{
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                padding: '4px 8px',
                fontSize: '12px',
              }}
            >
              <option value={3}>3 Filings</option>
              <option value={5}>5 Filings</option>
              <option value={10}>10 Filings</option>
            </select>
          </div>

          <button
            onClick={handleStartIngest}
            disabled={!currentCompany || ingestLoading || (!include10K && !include10Q)}
            className="btn btn-primary"
            style={{ padding: '8px 18px' }}
          >
            <DownloadCloud size={15} />
            {ingestLoading ? 'Initiating...' : `Ingest ${currentCompany?.ticker || 'Company'} Filings`}
          </button>
        </div>

        {ingestError && (
          <div style={{ marginTop: '12px', color: 'var(--accent-rose)', fontSize: '12px' }}>
            {ingestError}
          </div>
        )}

        {/* Live Active Job Status Bar */}
        {activeJob && (
          <div style={{
            marginTop: '16px',
            padding: '14px',
            backgroundColor: 'rgba(56, 189, 248, 0.05)',
            border: '1px solid rgba(56, 189, 248, 0.2)',
            borderRadius: 'var(--radius-md)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600 }}>
                {activeJob.status === 'completed' && <CheckCircle2 size={16} color="var(--accent-emerald)" />}
                {activeJob.status === 'running' && <RefreshCw size={16} color="var(--accent-cyan)" style={{ animation: 'spin 1s linear infinite' }} />}
                {activeJob.status === 'failed' && <AlertCircle size={16} color="var(--accent-rose)" />}
                <span>Job Status: {activeJob.status.toUpperCase()}</span>
              </div>
              <span className="mono" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                {activeJob.completed_filings} / {activeJob.total_filings || '?'} processed
              </span>
            </div>

            {/* Progress Bar */}
            <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255, 255, 255, 0.1)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${activeJob.total_filings > 0 ? (activeJob.completed_filings / activeJob.total_filings) * 100 : (activeJob.status === 'completed' ? 100 : 20)}%`,
                backgroundColor: activeJob.status === 'failed' ? 'var(--accent-rose)' : 'var(--accent-cyan)',
                transition: 'width 0.3s ease',
              }} />
            </div>

            {activeJob.error && (
              <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--accent-rose)' }}>
                Error: {activeJob.error}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filings Table Card */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: '15px', fontWeight: 700 }}>Available Filings ({filings.length})</h3>
          </div>

          <div style={{ display: 'flex', gap: '6px' }}>
            {['', '10-K', '10-Q'].map((f) => (
              <button
                key={f}
                onClick={() => setFormFilter(f)}
                className="btn btn-secondary"
                style={{
                  padding: '4px 10px',
                  fontSize: '11px',
                  backgroundColor: formFilter === f ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                  borderColor: formFilter === f ? 'var(--accent-cyan)' : 'var(--border-color)',
                  color: formFilter === f ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                }}
              >
                {f || 'All Forms'}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading filings...
          </div>
        ) : filings.length === 0 ? (
          <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
            No filings found for {currentCompany?.ticker}. Click "Ingest Filings" above to pull SEC filings from EDGAR.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '8px 12px' }}>Form</th>
                  <th style={{ padding: '8px 12px' }}>Period</th>
                  <th style={{ padding: '8px 12px' }}>Filing Date</th>
                  <th style={{ padding: '8px 12px' }}>Accession Number</th>
                  <th style={{ padding: '8px 12px' }}>Chunks Indexed</th>
                  <th style={{ padding: '8px 12px' }}>Status</th>
                  <th style={{ padding: '8px 12px', textAlign: 'right' }}>EDGAR Link</th>
                </tr>
              </thead>
              <tbody>
                {filings.map((filing) => (
                  <tr key={filing.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                    <td style={{ padding: '10px 12px' }}>
                      <span className={`badge ${filing.form_type === '10-K' ? 'badge-cyan' : 'badge-emerald'}`}>
                        {filing.form_type}
                      </span>
                    </td>
                    <td className="mono" style={{ padding: '10px 12px' }}>
                      {filing.fiscal_year ? `FY${filing.fiscal_year}` : '—'} {filing.fiscal_period ? `(${filing.fiscal_period})` : ''}
                    </td>
                    <td className="mono" style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>
                      {filing.filing_date}
                    </td>
                    <td className="mono" style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: '11px' }}>
                      {filing.accession_number}
                    </td>
                    <td className="mono" style={{ padding: '10px 12px' }}>
                      {filing.chunk_count}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {filing.is_processed ? (
                        <span className="badge badge-emerald"><CheckCircle2 size={10} /> INDEXED</span>
                      ) : (
                        <span className="badge badge-amber"><Clock size={10} /> DISCOVERED</span>
                      )}
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                      {filing.sec_filing_url && (
                        <a
                          href={filing.sec_filing_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: 'var(--accent-cyan)', display: 'inline-flex', alignItems: 'center', gap: '3px', textDecoration: 'none' }}
                        >
                          SEC <ExternalLink size={11} />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
