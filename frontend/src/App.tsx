import React, { useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { ResearchTab } from './components/ResearchTab';
import { MetricsTab } from './components/MetricsTab';
import { FilingsTab } from './components/FilingsTab';
import { EvaluationTab } from './components/EvaluationTab';
import { CitationModal } from './components/CitationModal';
import { Company, HealthStatus, SourceCitation } from './types';
import { fetchHealth, getCompany, searchCompanies } from './services/api';

export const App: React.FC = () => {
  const [currentCompany, setCurrentCompany] = useState<Company | null>(null);
  const [activeTab, setActiveTab] = useState<'research' | 'metrics' | 'filings' | 'eval'>('research');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<SourceCitation | null>(null);

  // Initialize health and default company (AAPL)
  useEffect(() => {
    fetchHealth()
      .then((h) => setHealth(h))
      .catch((e) => console.warn('Health check warning:', e));

    loadCompany('AAPL');
  }, []);

  const loadCompany = async (ticker: string) => {
    try {
      const comp = await getCompany(ticker);
      setCurrentCompany(comp);
    } catch {
      // Fallback: search SEC registry
      try {
        const results = await searchCompanies(ticker);
        if (results.length > 0) {
          setCurrentCompany(results[0]);
        }
      } catch (err) {
        console.error('Failed to load company:', err);
      }
    }
  };

  return (
    <div className="app-layout">
      {/* Top Navigation */}
      <Navbar
        currentCompany={currentCompany}
        onSelectCompany={loadCompany}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        health={health}
      />

      {/* Main Content Area */}
      <main className="app-main">
        {activeTab === 'research' && (
          <ResearchTab
            currentCompany={currentCompany}
            onOpenCitation={(c) => setSelectedCitation(c)}
          />
        )}

        {activeTab === 'metrics' && (
          <MetricsTab currentCompany={currentCompany} />
        )}

        {activeTab === 'filings' && (
          <FilingsTab
            currentCompany={currentCompany}
            onRefreshCompany={() => currentCompany && loadCompany(currentCompany.ticker)}
          />
        )}

        {activeTab === 'eval' && (
          <EvaluationTab />
        )}
      </main>

      {/* Citation Inspector Modal / Drawer */}
      <CitationModal
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  );
};

export default App;
