"""Unit tests for Reciprocal Rank Fusion (RRF)."""

from app.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_combines_rankings():
    dense_ranking = [
        {"id": "doc1", "content_preview": "Apple iPhone sales grew in 2023", "score": 0.95},
        {"id": "doc2", "content_preview": "Mac revenue remained steady", "score": 0.85},
    ]
    sparse_ranking = [
        {"id": "doc2", "content_preview": "Mac revenue remained steady", "score": 12.5},
        {"id": "doc3", "content_preview": "Services reached all time high", "score": 9.2},
    ]

    fused = reciprocal_rank_fusion([dense_ranking, sparse_ranking], k=60)

    # doc2 appeared in both rankings, so its combined RRF score should be highest
    assert len(fused) == 3
    assert fused[0]["id"] == "doc2"
    assert "rrf_score" in fused[0]


def test_rrf_empty_inputs():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []
