import React, { useState } from 'react';
import { Search, Database, Cpu, Activity, TrendingUp, FileText, BarChart3, FlaskConical } from 'lucide-react';
import { Company, HealthStatus } from '../types';

interface NavbarProps {
  currentCompany: Company | null;
  onSelectCompany: (ticker: string) => void;
  activeTab: 'research' | 'metrics' | 'filings' | 'eval';
  onSelectTab: (tab: 'research' | 'metrics' | 'filings' | 'eval') => void;
  health: HealthStatus | null;
}

const PRESET_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN'];

export const Navbar: React.FC<NavbarProps> = ({
  currentCompany,
  onSelectCompany,
  activeTab,
  onSelectTab,
  health,
}) => {
  const [searchInput, setSearchInput] = useState('');

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      onSelectCompany(searchInput.trim().toUpperCase());
      setSearchInput('');
    }
  };

  return (
    <header style={{
      borderBottom: '1px solid var(--border-color)',
      backgroundColor: 'rgba(7, 10, 18, 0.85)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 40,
    }}>
      <div style={{
        maxWidth: '1400px',
        margin: '0 auto',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(56, 189, 248, 0.3)',
          }}>
            <TrendingUp size={20} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 800, fontSize: '16px', letterSpacing: '-0.02em' }}>
                SEC Financial Intelligence
              </span>
              <span className="badge badge-cyan" style={{ fontSize: '10px' }}>PROD RAG</span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Multi-Year 10-K & 10-Q Research Engine
            </div>
          </div>
        </div>

        {/* Company Quick-Select & Search */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: '1', maxWidth: '480px' }}>
          <form onSubmit={handleSearchSubmit} style={{ position: 'relative', width: '100%' }}>
            <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '10px' }} />
            <input
              type="text"
              placeholder="Search ticker or CIK (e.g. AAPL, MSFT)..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px 8px 36px',
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '13px',
                outline: 'none',
              }}
            />
          </form>

          <div style={{ display: 'flex', gap: '4px' }}>
            {PRESET_TICKERS.map((ticker) => (
              <button
                key={ticker}
                onClick={() => onSelectCompany(ticker)}
                className="btn btn-secondary"
                style={{
                  padding: '6px 10px',
                  fontSize: '12px',
                  fontWeight: 600,
                  backgroundColor: currentCompany?.ticker === ticker ? 'rgba(56, 189, 248, 0.15)' : 'var(--bg-card)',
                  borderColor: currentCompany?.ticker === ticker ? 'var(--accent-cyan)' : 'var(--border-color)',
                  color: currentCompany?.ticker === ticker ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                }}
              >
                {ticker}
              </button>
            ))}
          </div>
        </div>

        {/* System Status Indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {health?.limited_mode ? (
            <div className="badge badge-amber" title="Generation disabled, deterministic retrieval active">
              <Cpu size={12} /> LIMITED MODE
            </div>
          ) : (
            <div className="badge badge-emerald" title={`AI Provider: ${health?.ai_chat_provider || 'Active'}`}>
              <Cpu size={12} /> AI READY ({health?.ai_chat_provider || 'Gemini'})
            </div>
          )}

          <div className="badge badge-cyan" title="Database Connected">
            <Database size={12} /> DB ONLINE
          </div>
        </div>
      </div>

      {/* Navigation Sub-bar */}
      <div style={{
        maxWidth: '1400px',
        margin: '0 auto',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderTop: '1px solid rgba(255, 255, 255, 0.05)',
      }}>
        {/* Active Company Breadcrumb */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 0', fontSize: '13px' }}>
          <span style={{ color: 'var(--text-muted)' }}>Focus Company:</span>
          {currentCompany ? (
            <span style={{ fontWeight: 700, color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className="mono">{currentCompany.ticker}</span>
              <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}>({currentCompany.name})</span>
            </span>
          ) : (
            <span style={{ color: 'var(--accent-amber)', fontStyle: 'italic' }}>None Selected</span>
          )}
        </div>

        {/* Tabs */}
        <nav style={{ display: 'flex', gap: '2px' }}>
          {[
            { id: 'research', label: 'Research & RAG', icon: Activity },
            { id: 'metrics', label: 'Financial Statements & Ratios', icon: BarChart3 },
            { id: 'filings', label: 'Filings & Ingestion', icon: FileText },
            { id: 'eval', label: 'Evaluation & Benchmarks', icon: FlaskConical },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onSelectTab(id as any)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 16px',
                fontSize: '13px',
                fontWeight: activeTab === id ? 600 : 500,
                color: activeTab === id ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                backgroundColor: 'transparent',
                border: 'none',
                borderBottom: activeTab === id ? '2px solid var(--accent-cyan)' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  );
};
