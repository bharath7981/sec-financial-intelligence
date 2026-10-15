import React, { useEffect, useState } from 'react';
import { BarChart3, TrendingUp, TrendingDown, DollarSign, Percent, ShieldCheck, RefreshCw } from 'lucide-react';
import { Company } from '../types';
import { getMetrics } from '../services/api';

interface MetricsTabProps {
  currentCompany: Company | null;
}

export const MetricsTab: React.FC<MetricsTabProps> = ({ currentCompany }) => {
  const [data, setData] = useState<{ facts: any[]; calculated_metrics: any[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCompanyMetrics = async () => {
    if (!currentCompany) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getMetrics(currentCompany.ticker);
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch financial metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompanyMetrics();
  }, [currentCompany?.ticker]);

  const formatCurrency = (val: number | null | undefined) => {
    if (val === null || val === undefined) return '—';
    if (Math.abs(val) >= 1_000_000_000) {
      return `$${(val / 1_000_000_000).toFixed(2)}B`;
    }
    if (Math.abs(val) >= 1_000_000) {
      return `$${(val / 1_000_000).toFixed(2)}M`;
    }
    return `$${val.toLocaleString()}`;
  };

  const formatPercent = (val: number | null | undefined) => {
    if (val === null || val === undefined) return '—';
    return `${val.toFixed(2)}%`;
  };

  // Group facts by concept -> fiscal_year -> value
  const factsMap: Record<string, Record<number, number>> = {};
  const yearsSet = new Set<number>();

  if (data?.facts) {
    for (const f of data.facts) {
      if (!factsMap[f.concept]) factsMap[f.concept] = {};
      factsMap[f.concept][f.fiscal_year] = f.value;
      yearsSet.add(f.fiscal_year);
    }
  }

  const sortedYears = Array.from(yearsSet).sort((a, b) => b - a);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BarChart3 size={20} color="var(--accent-cyan)" />
            Multi-Year Financial Statements & Ratios
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            XBRL normalized figures extracted directly from 10-K & 10-Q annual filings
          </p>
        </div>

        <button
          onClick={fetchCompanyMetrics}
          disabled={!currentCompany || loading}
          className="btn btn-secondary"
          style={{ fontSize: '12px', padding: '6px 12px' }}
        >
          <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Refresh Metrics
        </button>
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          Loading financial data for {currentCompany?.ticker}...
        </div>
      )}

      {error && (
        <div className="card" style={{ border: '1px solid var(--accent-rose)', color: 'var(--accent-rose)', padding: '16px' }}>
          {error}
        </div>
      )}

      {/* Main Content */}
      {data && !loading && (
        <>
          {/* Ratio Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
            {data.calculated_metrics && data.calculated_metrics.slice(0, 4).map((m: any, idx: number) => (
              <div key={idx} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>
                    {m.metric.replace(/_/g, ' ').toUpperCase()}
                  </span>
                  <span className="badge badge-emerald">FY{m.fiscal_year}</span>
                </div>
                <div className="mono" style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {m.unit === '%' ? formatPercent(m.value) : (m.unit === 'USD' ? formatCurrency(m.value) : m.value?.toFixed(2))}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Formula: <span className="mono">{m.formula || 'Direct XBRL'}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Detailed Statement Table */}
          <div className="card">
            <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '14px' }}>
              Standardized Financial Statement Line Items
            </h3>
            {sortedYears.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                No ingested financial statements for {currentCompany?.ticker} yet. Visit the "Filings & Ingestion" tab to ingest filings.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '10px 14px' }}>Standard Concept</th>
                      {sortedYears.map((y) => (
                        <th key={y} className="mono" style={{ padding: '10px 14px', textAlign: 'right' }}>
                          FY{y}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { concept: 'revenue', label: 'Total Revenue', highlight: true },
                      { concept: 'gross_profit', label: 'Gross Profit' },
                      { concept: 'operating_income', label: 'Operating Income' },
                      { concept: 'net_income', label: 'Net Income (Loss)', highlight: true },
                      { concept: 'operating_cash_flow', label: 'Operating Cash Flow' },
                      { concept: 'capital_expenditures', label: 'Capital Expenditures (CapEx)' },
                      { concept: 'total_assets', label: 'Total Assets' },
                      { concept: 'total_liabilities', label: 'Total Liabilities' },
                      { concept: 'stockholders_equity', label: "Stockholders' Equity" },
                    ].map(({ concept, label, highlight }) => (
                      <tr
                        key={concept}
                        style={{
                          borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                          backgroundColor: highlight ? 'rgba(56, 189, 248, 0.03)' : 'transparent',
                        }}
                      >
                        <td style={{ padding: '10px 14px', fontWeight: highlight ? 700 : 500, color: highlight ? 'var(--accent-cyan)' : 'var(--text-primary)' }}>
                          {label}
                        </td>
                        {sortedYears.map((y) => {
                          const val = factsMap[concept]?.[y];
                          return (
                            <td
                              key={y}
                              className="mono"
                              style={{
                                padding: '10px 14px',
                                textAlign: 'right',
                                fontWeight: highlight ? 700 : 400,
                                color: val !== undefined && val < 0 ? 'var(--accent-rose)' : 'inherit',
                              }}
                            >
                              {formatCurrency(val)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
