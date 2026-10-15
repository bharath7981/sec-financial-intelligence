import React, { useEffect, useState } from 'react';
import { X, ExternalLink, FileText, ShieldCheck, Layers, BookOpen } from 'lucide-react';
import { SourceCitation } from '../types';
import { getChunkDetail } from '../services/api';

interface CitationModalProps {
  citation: SourceCitation | null;
  onClose: () => void;
}

export const CitationModal: React.FC<CitationModalProps> = ({ citation, onClose }) => {
  const [chunkDetail, setChunkDetail] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [showParent, setShowParent] = useState(false);

  useEffect(() => {
    if (!citation?.chunk_id) {
      setChunkDetail(null);
      return;
    }

    setLoading(true);
    getChunkDetail(citation.chunk_id)
      .then((res) => {
        setChunkDetail(res);
      })
      .catch((err) => {
        console.warn('Could not load full chunk details:', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [citation?.chunk_id]);

  if (!citation) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{
          maxWidth: '800px',
          width: '100%',
          maxHeight: '85vh',
          overflowY: 'auto',
          backgroundColor: '#0d131f',
          border: '1px solid var(--accent-violet)',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.8), 0 0 30px rgba(168, 85, 247, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge badge-violet">{citation.source_id}</span>
            <span style={{ fontWeight: 700, fontSize: '15px' }}>
              {citation.section || 'SEC Filing Disclosure'}
            </span>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Metadata Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '10px',
          background: 'rgba(255, 255, 255, 0.02)',
          padding: '12px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-color)',
          fontSize: '12px',
        }}>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Form: </span>
            <span className="badge badge-cyan">{citation.form_type || '10-K'}</span>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Period: </span>
            <span className="mono" style={{ fontWeight: 600 }}>FY{citation.fiscal_year || '—'}</span>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Filing Date: </span>
            <span className="mono">{citation.filing_date || '—'}</span>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Relevance: </span>
            <span className="mono" style={{ color: 'var(--accent-emerald)' }}>
              {citation.relevance_score ? citation.relevance_score.toFixed(3) : 'High'}
            </span>
          </div>
        </div>

        {/* Parent / Child Context Toggle */}
        {chunkDetail?.parent_content && (
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => setShowParent(false)}
              className="btn btn-secondary"
              style={{
                fontSize: '11px',
                padding: '4px 10px',
                backgroundColor: !showParent ? 'rgba(168, 85, 247, 0.2)' : 'transparent',
                borderColor: !showParent ? 'var(--accent-violet)' : 'var(--border-color)',
                color: !showParent ? 'var(--accent-violet)' : 'var(--text-secondary)',
              }}
            >
              <BookOpen size={12} /> Target Chunk Passage
            </button>
            <button
              onClick={() => setShowParent(true)}
              className="btn btn-secondary"
              style={{
                fontSize: '11px',
                padding: '4px 10px',
                backgroundColor: showParent ? 'rgba(168, 85, 247, 0.2)' : 'transparent',
                borderColor: showParent ? 'var(--accent-violet)' : 'var(--border-color)',
                color: showParent ? 'var(--accent-violet)' : 'var(--text-secondary)',
              }}
            >
              <Layers size={12} /> Expanded Parent Context
            </button>
          </div>
        )}

        {/* Verbatim Content Box */}
        <div style={{
          backgroundColor: 'var(--bg-input)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)',
          padding: '16px',
          fontSize: '13px',
          lineHeight: '1.6',
          fontFamily: showParent ? 'inherit' : 'var(--font-mono)',
          whiteSpace: 'pre-wrap',
          maxHeight: '350px',
          overflowY: 'auto',
          color: '#e2e8f0',
        }}>
          {loading ? (
            <div style={{ color: 'var(--text-muted)' }}>Loading full text...</div>
          ) : showParent && chunkDetail?.parent_content ? (
            chunkDetail.parent_content
          ) : (
            chunkDetail?.content || citation.content_preview
          )}
        </div>

        {/* Accession & Link */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-color)', paddingTop: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
          <span className="mono">
            Accession: {citation.accession_number || '0000320193-23-000106'}
          </span>

          {citation.source_url && (
            <a
              href={citation.source_url}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary"
              style={{ fontSize: '11px', padding: '4px 12px', textDecoration: 'none' }}
            >
              Verify on SEC EDGAR <ExternalLink size={12} />
            </a>
          )}
        </div>
      </div>
    </div>
  );
};
