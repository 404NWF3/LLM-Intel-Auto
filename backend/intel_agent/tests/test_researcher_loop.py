"""Real estimator checks for the small, bounded research loop."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from pydantic import ValidationError
from sklearn.metrics import average_precision_score, roc_auc_score

from intel_agent.researcher import loop
from intel_agent.researcher.schemas import ResearchRequest
from intel_agent.runtime.structured import StructuredDecisionEngine


def _dataset(tmp_path: Path, *, labeled: bool = True) -> tuple[Path, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(7)
    X = np.vstack([rng.normal(size=(100, 4)), rng.normal(loc=4, size=(20, 4))])
    X[::17, 1] = np.nan
    y = np.r_[np.zeros(100, dtype=int), np.ones(20, dtype=int)]
    path = tmp_path / "data.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["a", "b", "c", "d"] + (["label"] if labeled else []))
        for index, row in enumerate(X):
            writer.writerow(["" if np.isnan(value) else value for value in row] + ([y[index]] if labeled else []))
    return path, X, y


def _config(*, labeled: bool = True, rounds: int = 3, use_llm: bool = False) -> ResearchRequest:
    return ResearchRequest(dataset_id="ds_" + "a" * 32, label_column="label" if labeled else None,
                           max_rounds=rounds, use_llm=use_llm)


def test_labeled_real_models_keep_frozen_validation_and_test(tmp_path, monkeypatch):
    path, X, y = _dataset(tmp_path)
    expected_test = X[loop._split_indices(y, len(X))["test"]]
    score_model = loop._scores
    test_calls = []

    def track_scores(model, data):
        if np.array_equal(data, expected_test, equal_nan=True):
            test_calls.append(True)
        return score_model(model, data)

    monkeypatch.setattr(loop, "_scores", track_scores)
    snapshots = []
    state = loop.run_research(_config(), path, tmp_path / "output", snapshots.append)
    assert [entry["model"] for entry in state["rounds"]] == ["isolation_forest", "lof", "pca"]
    assert all(entry["status"] != "failed" for entry in state["rounds"])
    assert state["metric"] == "validation_ap"
    best = max(state["rounds"], key=lambda entry: entry["score"])
    assert state["best_round"] == best["round"]
    artifact = joblib.load(tmp_path / "output" / "model.joblib")
    splits = artifact["split_indices"]
    assert [len(splits[name]) for name in ["train", "validation", "test"]] == [72, 24, 24]
    assert len(set().union(*(set(indices) for indices in splits.values()))) == len(X)
    assert sum(len(indices) for indices in splits.values()) == len(X)
    np.testing.assert_allclose(artifact["pipeline"].named_steps["imputer"].statistics_,
                               np.nanmedian(X[splits["train"]], axis=0))
    test_scores = -artifact["pipeline"].score_samples(X[splits["test"]])
    assert state["final_metrics"]["ap"] == pytest.approx(average_precision_score(y[splits["test"]], test_scores))
    assert state["final_metrics"]["auroc"] == pytest.approx(roc_auc_score(y[splits["test"]], test_scores))
    with (tmp_path / "output" / "scores.csv").open() as handle:
        records = list(csv.DictReader(handle))
    assert len(records) == len(X)
    assert {record["split"] for record in records} == {"train", "validation", "test"}
    assert snapshots[0]["rounds"] == []  # Progress history is not mutated in place.
    assert all(snapshot["final_metrics"] is None for snapshot in snapshots[:-1])
    assert len(test_calls) == 1


def test_unlabeled_real_bootstrap_stability_and_reload(tmp_path):
    path, X, _ = _dataset(tmp_path, labeled=False)
    state = loop.run_research(_config(labeled=False), path, tmp_path / "output", lambda _: None)
    assert state["metric"] == "rank_stability"
    assert "不是准确率" in state["evaluation_note"]
    assert state["final_metrics"] is None
    assert all(0 <= entry["score"] <= 1 for entry in state["rounds"])
    artifact = joblib.load(tmp_path / "output" / "model.joblib")
    assert set(artifact["split_indices"]) == {"train", "reference"}
    assert np.all(np.isfinite(-artifact["pipeline"].score_samples(X[:3])))
    repeated = loop.run_research(_config(labeled=False), path, tmp_path / "repeat", lambda _: None)
    np.testing.assert_allclose([entry["score"] for entry in state["rounds"]],
                               [entry["score"] for entry in repeated["rounds"]])
    assert loop._rank_agreement(np.ones(4), np.ones(4)) == 0
    assert loop._rank_agreement(np.arange(4), -np.arange(4)) == pytest.approx(0)


def test_structured_llm_plan_invalid_and_duplicate_fall_back(tmp_path, monkeypatch):
    path, _, _ = _dataset(tmp_path)
    replies = iter([
        {"model": "pca", "params": {"n_components": 0.8}, "reason": "检验低维结构。"},
        {"model": "pca", "params": {"n_components": 0.8}, "reason": "重复。"},
        {"model": "lof", "params": {"n_neighbors": 10, "execute": 1}, "reason": "非法参数。"},
    ])
    calls = []

    async def runner(prompt, schema, system_prompt, model, max_turns):
        calls.append(prompt)
        assert max_turns == 2
        assert schema["additionalProperties"] is False
        profile = json.loads(prompt)["data_profile"]
        assert profile["evaluation_mode"] == "label_assisted_selection"
        assert profile["validation_labels_available"] is True
        assert profile["training_uses_labels"] is False
        assert "真实 0/1 标签计算的 AP" in system_prompt
        return next(replies)

    engine = StructuredDecisionEngine(runner=runner, timeout_seconds=25, max_turns=2)
    monkeypatch.setattr(loop, "StructuredDecisionEngine", lambda **kwargs: engine)
    state = loop.run_research(_config(rounds=4, use_llm=True), path, tmp_path / "output", lambda _: None)
    assert [entry["planner"] for entry in state["rounds"]] == ["baseline", "llm", "fallback", "fallback"]
    assert state["rounds"][1]["params"] == {"n_components": 0.8}
    assert len(calls) == 3
    assert all("final_metrics" not in prompt for prompt in calls)
    assert len({(entry["model"], str(entry["params"])) for entry in state["rounds"]}) == 4


@pytest.mark.parametrize("model,params", [
    ("isolation_forest", {"n_estimators": 1000000}),
    ("isolation_forest", {"n_jobs": -1}),
    ("lof", {"n_neighbors": True}),
    ("lof", {"n_neighbors": 2.5}),
    ("pca", {"n_components": float("nan")}),
    ("pca", {"n_components": 1.0}),
])
def test_candidate_parameter_contract(model, params):
    with pytest.raises(ValidationError):
        loop.Candidate(model=model, params=params, reason="invalid")


def test_failed_round_preserves_best_and_disabled_llm_makes_no_calls(tmp_path, monkeypatch):
    path, _, _ = _dataset(tmp_path)
    evaluate = loop._evaluate_candidate

    def fail_lof(candidate, *args):
        if candidate.model == "lof":
            raise RuntimeError("simulated estimator failure")
        return evaluate(candidate, *args)

    def no_llm(**kwargs):
        raise AssertionError("LLM must not be constructed when disabled")

    monkeypatch.setattr(loop, "_evaluate_candidate", fail_lof)
    monkeypatch.setattr(loop, "StructuredDecisionEngine", no_llm)
    state = loop.run_research(_config(rounds=2), path, tmp_path / "output", lambda _: None)
    assert state["best_round"] == 1
    assert state["rounds"][0]["status"] == "keep"
    assert state["rounds"][1]["status"] == "failed"
    assert state["rounds"][1]["score"] is None
    assert "simulated estimator failure" in state["rounds"][1]["error"]
    assert (tmp_path / "output" / "model.joblib").exists()
    assert state["final_metrics"] is not None


def test_all_failed_produces_no_artifacts(tmp_path, monkeypatch):
    path, _, _ = _dataset(tmp_path)

    def fail(*args):
        raise RuntimeError("unavailable estimator")

    monkeypatch.setattr(loop, "_evaluate_candidate", fail)
    snapshots = []
    with pytest.raises(ValueError, match="所有实验均失败"):
        loop.run_research(_config(rounds=2), path, tmp_path / "output", snapshots.append)
    state = snapshots[-1]
    assert state["best_round"] is None
    assert len(state["rounds"]) == 2
    assert state["final_metrics"] is None
    assert not (tmp_path / "output").exists()


def test_lof_training_export_uses_fitted_outlier_factors(tmp_path, monkeypatch):
    path, _, _ = _dataset(tmp_path)
    evaluate = loop._evaluate_candidate

    def favor_lof(candidate, *args):
        model, _ = evaluate(candidate, *args)
        return model, 1.0 if candidate.model == "lof" else 0.0

    monkeypatch.setattr(loop, "_evaluate_candidate", favor_lof)
    state = loop.run_research(_config(rounds=2), path, tmp_path / "output", lambda _: None)
    assert state["best_round"] == 2
    artifact = joblib.load(tmp_path / "output" / "model.joblib")
    assert artifact["pipeline"].named_steps["detector"].novelty is True
    with (tmp_path / "output" / "scores.csv").open() as handle:
        training = [row for row in csv.DictReader(handle) if row["split"] == "train"]
    np.testing.assert_allclose([float(row["anomaly_score"]) for row in training],
                               -artifact["pipeline"].named_steps["detector"].negative_outlier_factor_)


def test_small_class_rejected_before_experiments():
    with pytest.raises(ValueError, match="至少 5"):
        loop._split_indices(np.r_[np.zeros(19), 1], 20)
