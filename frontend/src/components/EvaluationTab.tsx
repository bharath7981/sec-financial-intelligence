import React, { useEffect, useState } from 'react';
import { FlaskConical, Play, CheckCircle2, XCircle, Clock, ShieldCheck, RefreshCw, BarChart2 } from 'lucide-react';
import { EvaluationRun } from '../types';
import { listEvaluations, runEvaluation, getEvaluation } from '../services/api';

export const EvaluationTab: React.FC = () => {
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvaluationRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [runningEval, setRunningEval] = useState(false);

  // Run config
  const [retrievalMode, setRetrievalMode] = useState('hybrid');
  const [useReranker, setUseReranker] = useState(true);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const data = await listEvaluations();
      setRuns(data);
      if (data.length > 0 && !selectedRun) {
        setSelectedRun(data[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  // Poll running benchmark if any
  useEffect(() => {
    if (!selectedRun || selectedRun.status !== 'running') return;

    const interval = setInterval(async () => {
      try {
        const updated = await getEvaluation(selectedRun.id);
        setSelectedRun(updated);
        if (updated.status === 'completed' || updated.status === 'failed') {
          fetchRuns();
        }
      } catch (err) {
        console.error(err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [selectedRun?.id, selectedRun?.status]);

  const handleStartRun = async () => {
    setRunningEval(true);
    try {
      const newRun = await runEvaluation({
        retrieval_mode: retrievalMode,
        use_reranker: useReranker,
      });
      setSelectedRun(newRun);
      fetchRuns();
    } catch (err) {
      console.error('Failed to trigger eval:', err);
    } finally {
      setRunningEval(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Benchmark Control Bar */}
      <div className="card" style={{ border: '1px solid var(--border-highlight)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FlaskConical size={18} color="var(--accent-cyan)" />
              RAG Evaluation & Strategy Benchmarking
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Tests golden questions across extraction, calculation, multi-year comparison, and boundary cases.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
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
                }}
              >
                <option value="hybrid">Hybrid RRF</option>
                <option value="dense">Dense Only</option>
                <option value="sparse">Sparse BM25 Only</option>
              </select>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={useReranker}
                onChange={(e) => setUseReranker(e.target.checked)}
                style={{ accentColor: 'var(--accent-cyan)' }}
              />
              Reranker
            </label>

            <button
              onClick={handleStartRun}
              disabled={runningEval || selectedRun?.status === 'running'}
              className="btn btn-primary"
              style={{ fontSize: '12px', padding: '6px 14px' }}
            >
              <Play size={13} />
              {selectedRun?.status === 'running' ? 'Running Benchmark...' : 'Run Benchmark'}
            </button>
          </div>
        </div>
      </div>

      {/* Benchmark History & Metrics Comparison */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px' }}>
        {/* Left: Runs List */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 700 }}>Benchmark Runs</h3>
            <button onClick={fetchRuns} className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: '11px' }}>
              <RefreshCw size={11} />
            </button>
          </div>

          {runs.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
              No benchmark runs yet. Click "Run Benchmark" above.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '500px', overflowY: 'auto' }}>
              {runs.map((r) => (
                <div
                  key={r.id}
                  onClick={() => setSelectedRun(r)}
                  style={{
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: selectedRun?.id === r.id ? 'rgba(56, 189, 248, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                    border: selectedRun?.id === r.id ? '1px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '12px', fontWeight: 600 }}>{r.name}</span>
                    <span className={`badge ${r.status === 'completed' ? 'badge-emerald' : (r.status === 'running' ? 'badge-cyan' : 'badge-amber')}`}>
                      {r.status}
                    </span>
                  </div>

                  {r.results_summary && (
                    <div style={{ display: 'flex', gap: '10px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                      <span>Acc: {(r.results_summary.accuracy * 100).toFixed(0)}%</span>
                      <span>Cit: {(r.results_summary.citation_coverage * 100).toFixed(0)}%</span>
                      <span>{r.results_summary.avg_latency_ms}ms</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Selected Run Details & Question Breakdown */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {selectedRun ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
                <div>
                  <h3 style={{ fontSize: '15px', fontWeight: 700 }}>{selectedRun.name}</h3>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Strategy: {selectedRun.config?.retrieval_mode || 'hybrid'} &bull; Reranker: {selectedRun.config?.use_reranker ? 'Enabled' : 'Disabled'}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <span className="badge badge-cyan">
                    Progress: {selectedRun.completed_questions} / {selectedRun.total_questions}
                  </span>
                </div>
              </div>

              {/* KPI Score Cards */}
              {selectedRun.results_summary && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
                  <div className="card" style={{ padding: '12px', backgroundColor: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Grounding / Accuracy</div>
                    <div className="mono" style={{ fontSize: '20px', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                      {(selectedRun.results_summary.accuracy * 100).toFixed(1)}%
                    </div>
                  </div>

                  <div className="card" style={{ padding: '12px', backgroundColor: 'rgba(168, 85, 247, 0.05)', border: '1px solid rgba(168, 85, 247, 0.2)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Citation Coverage</div>
                    <div className="mono" style={{ fontSize: '20px', fontWeight: 700, color: 'var(--accent-violet)' }}>
                      {(selectedRun.results_summary.citation_coverage * 100).toFixed(1)}%
                    </div>
                  </div>

                  <div className="card" style={{ padding: '12px', backgroundColor: 'rgba(56, 189, 248, 0.05)', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Average Latency</div>
                    <div className="mono" style={{ fontSize: '20px', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {selectedRun.results_summary.avg_latency_ms}ms
                    </div>
                  </div>
                </div>
              )}

              {/* Question Level Audit */}
              <h4 style={{ fontSize: '13px', fontWeight: 700, marginTop: '8px' }}>Golden Question Test Results</h4>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '8px' }}>Status</th>
                      <th style={{ padding: '8px' }}>Test Question</th>
                      <th style={{ padding: '8px' }}>Category</th>
                      <th style={{ padding: '8px' }}>Citations</th>
                      <th style={{ padding: '8px', textAlign: 'right' }}>Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRun.results_summary?.details?.map((q, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                        <td style={{ padding: '8px' }}>
                          {q.passed ? (
                            <span className="badge badge-emerald"><CheckCircle2 size={10} /> PASS</span>
                          ) : (
                            <span className="badge badge-rose"><XCircle size={10} /> FAIL</span>
                          )}
                        </td>
                        <td style={{ padding: '8px', fontWeight: 500 }}>{q.question}</td>
                        <td style={{ padding: '8px' }}>
                          <span className="badge badge-cyan" style={{ fontSize: '10px' }}>{q.category}</span>
                        </td>
                        <td className="mono" style={{ padding: '8px' }}>{q.citations_count || 0}</td>
                        <td className="mono" style={{ padding: '8px', textAlign: 'right', color: 'var(--text-muted)' }}>
                          {q.latency_ms ? `${q.latency_ms}ms` : '—'}
                        </td>
                      </tr>
                    )) || (
                      <tr>
                        <td colSpan={5} style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                          {selectedRun.status === 'running' ? 'Running evaluation across golden questions...' : 'No details available.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
              Select a benchmark run to view results
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
