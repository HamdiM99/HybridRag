"""Tests de la fusion RRF (fonction pure, aucun appel réseau)."""
import pytest

from cvsearch.search.hybrid import RRF_K, fuse_rankings


def test_candidate_found_by_both_retrievers_beats_single_retriever():
    # A : 1er partout ; B : 2e du dense seulement ; C : 3e du dense ET 2e du BM25.
    fused = fuse_rankings([["A", "B", "C"], ["A", "C"]])
    ranked = sorted(fused, key=fused.get, reverse=True)
    assert ranked == ["A", "C", "B"]  # C (deux listes) devance B (une seule)
    assert fused["A"] == pytest.approx(2 / (RRF_K + 1))
    assert fused["C"] == pytest.approx(1 / (RRF_K + 3) + 1 / (RRF_K + 2))
    assert fused["B"] == pytest.approx(1 / (RRF_K + 2))


def test_chunks_of_same_candidate_do_not_add_up_within_a_retriever():
    # A occupe les 3 premiers chunks du dense : seul son meilleur chunk compte,
    # et B devient 2e candidat (rang parmi les candidats distincts).
    fused = fuse_rankings([["A", "A", "A", "B"], ["B"]])
    assert fused["A"] == pytest.approx(1 / (RRF_K + 1))
    assert fused["B"] == pytest.approx(1 / (RRF_K + 2) + 1 / (RRF_K + 1))
    assert fused["B"] > fused["A"]


def test_single_retriever_preserves_its_order():
    fused = fuse_rankings([["X", "Y", "Z"]])
    assert sorted(fused, key=fused.get, reverse=True) == ["X", "Y", "Z"]


def test_empty_rankings():
    assert fuse_rankings([]) == {}
    assert fuse_rankings([[], []]) == {}


def test_k_changes_the_gap_between_ranks():
    small_k = fuse_rankings([["A", "B"]], k=10)
    large_k = fuse_rankings([["A", "B"]], k=200)
    assert small_k["A"] / small_k["B"] > large_k["A"] / large_k["B"]
