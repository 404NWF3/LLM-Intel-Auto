"""Bounded anomaly-model experiments with a fixed, label-aware evaluation plan."""

from __future__ import annotations

import csv
import json
import math
import time
from copy import deepcopy
from pathlib import Path
from typing import Callable, Literal

import joblib
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy.stats import rankdata
from sklearn.base import BaseEstimator
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..runtime.structured import StructuredDecisionEngine
from .data import load_dataset
from .schemas import ResearchRequest

SEED = 42
BOOTSTRAP_REPEATS = 3
DEFAULT_PARAMS = {
    "isolation_forest": {"n_estimators": 100, "max_samples": 1.0, "max_features": 1.0},
    "lof": {"n_neighbors": 20},
    "pca": {"n_components": 0.9},
}


class Candidate(BaseModel):
    """Only numeric, bounded estimator options can cross the planning boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)
    model: Literal["isolation_forest", "lof", "pca"]
    params: dict[str, int | float] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_parameters(self) -> "Candidate":
        if set(self.params) - set(DEFAULT_PARAMS[self.model]):
            raise ValueError("unsupported estimator parameter")
        params = DEFAULT_PARAMS[self.model] | self.params
        for key, value in params.items():
            if isinstance(value, bool) or not math.isfinite(value):
                raise ValueError("parameters must be finite numbers")
            if key == "n_estimators":
                if not isinstance(value, int) or not 50 <= value <= 300:
                    raise ValueError("n_estimators must be an integer in [50, 300]")
            elif key == "n_neighbors":
                if not isinstance(value, int) or not 2 <= value <= 80:
                    raise ValueError("n_neighbors must be an integer in [2, 80]")
            elif key == "n_components":
                if not 0.5 <= value <= 0.99:
                    raise ValueError("n_components must be a variance fraction in [0.5, 0.99]")
                params[key] = float(value)
            elif not 0.2 <= value <= 1.0:
                raise ValueError(f"{key} must be a fraction in [0.2, 1.0]")
            else:
                params[key] = float(value)
        self.params = params
        return self


class PCAReconstruction(BaseEstimator):
    """Expose PCA reconstruction as normality scores, like the other detectors."""

    def __init__(self, n_components: float = 0.9):
        self.n_components = n_components

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> "PCAReconstruction":
        self.pca_ = PCA(n_components=self.n_components, svd_solver="full").fit(X)
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        reconstructed = self.pca_.inverse_transform(self.pca_.transform(X))
        return -np.mean(np.square(X - reconstructed), axis=1)


def _pipeline(candidate: Candidate, train_size: int, seed: int = SEED) -> Pipeline:
    params = dict(candidate.params)
    if candidate.model == "isolation_forest":
        detector = IsolationForest(**params, random_state=seed, n_jobs=1)
    elif candidate.model == "lof":
        params["n_neighbors"] = min(params["n_neighbors"], train_size - 1)
        detector = LocalOutlierFactor(**params, novelty=True, n_jobs=1)
    else:
        detector = PCAReconstruction(**params)
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
        ("detector", detector),
    ])


def _scores(model: Pipeline, X: np.ndarray) -> np.ndarray:
    scores = -np.asarray(model.score_samples(X), dtype=float)
    if scores.shape != (len(X),) or not np.all(np.isfinite(scores)):
        raise ValueError("detector returned invalid anomaly scores")
    return scores


def _rank_agreement(first: np.ndarray, second: np.ndarray) -> float:
    # Constant predictions contain no ordering evidence, even when reproducible.
    if np.ptp(first) <= 1e-12 or np.ptp(second) <= 1e-12:
        return 0.0
    correlation = float(np.corrcoef(rankdata(first), rankdata(second))[0, 1])
    return float(np.clip((correlation + 1.0) / 2.0, 0.0, 1.0))


def _evaluate_candidate(
    candidate: Candidate,
    X_train: np.ndarray,
    X_reference: np.ndarray,
    y_reference: np.ndarray | None,
) -> tuple[Pipeline, float]:
    model = _pipeline(candidate, len(X_train)).fit(X_train)
    reference_scores = _scores(model, X_reference)
    if y_reference is not None:
        return model, float(average_precision_score(y_reference, reference_scores))
    rng = np.random.default_rng(SEED)
    agreements = []
    for repeat in range(BOOTSTRAP_REPEATS):
        indices = rng.integers(0, len(X_train), size=len(X_train))
        refitted = _pipeline(candidate, len(X_train), SEED + repeat + 1).fit(X_train[indices])
        agreements.append(_rank_agreement(reference_scores, _scores(refitted, X_reference)))
    return model, float(np.mean(agreements))


def _candidate_key(candidate: Candidate) -> str:
    return json.dumps([candidate.model, candidate.params], sort_keys=True)


def _fit_to_data(candidate: Candidate, train_size: int) -> Candidate:
    if candidate.model == "lof" and candidate.params["n_neighbors"] >= train_size:
        candidate = candidate.model_copy(update={"params": {"n_neighbors": train_size - 1}})
    return candidate


def _fallback_candidates():
    # Cover all three model families before spending more budget on one family.
    yield Candidate(model="lof", params={"n_neighbors": 20}, reason="比较局部密度模型与隔离森林基线。")
    yield Candidate(model="pca", params={"n_components": 0.9}, reason="检查线性重构误差是否提供更好的异常排序。")
    for index, (trees, fraction) in enumerate([(200, 0.6), (100, 0.5), (200, 1.0), (300, 0.8)]):
        yield Candidate(model="isolation_forest", params={"n_estimators": trees, "max_samples": fraction}, reason="在受限范围内改变树数量和采样比例。")
        yield Candidate(model="lof", params={"n_neighbors": [10, 5, 35, 50][index]}, reason="检验局部密度对邻域大小的敏感性。")
        yield Candidate(model="pca", params={"n_components": [0.7, 0.8, 0.95, 0.99][index]}, reason="检验重构模型对保留方差比例的敏感性。")
    for trees in [50, 150, 250, 300]:
        for fraction in [0.4, 0.7, 1.0]:
            yield Candidate(model="isolation_forest", params={"n_estimators": trees, "max_samples": fraction, "max_features": 0.8}, reason="继续比较有界隔离森林配置。")


def _plan_candidate(engine, profile: dict, rounds: list[dict], seen: set[str]) -> tuple[Candidate, str]:
    if engine is not None:
        try:
            evaluation_instruction = (
                "当前为有标签辅助选模：validation_ap 是使用独立验证集真实 0/1 标签计算的 AP，越大越好。"
                "模型训练不使用标签，但选模使用验证标签；不能把当前分数称为排名稳定性或把选模称为无监督。"
                if profile["evaluation_mode"] == "label_assisted_selection" else
                "当前完全没有可用标签：rank_stability 是固定参考集上的 bootstrap 排序稳定性代理，越大越稳定。"
                "当前分数不是 AP、准确率或真实检测效果；不能声称通过真实标签验证了模型。"
            )
            planned = engine.decide(
                "researcher_candidate",
                json.dumps({"data_profile": profile, "previous_rounds": rounds,
                            "allowed_parameters": {"isolation_forest": {"n_estimators": "integer 50..300", "max_samples": "fraction 0.2..1", "max_features": "fraction 0.2..1"}, "lof": {"n_neighbors": "integer 2..80"}, "pca": {"n_components": "variance fraction 0.5..0.99"}}}, ensure_ascii=False),
                Candidate,
                system_prompt=("为异常检测选择下一组模型和参数。仅提交一个未试过的合法配置及简短中文理由。"
                               + evaluation_instruction + "根据当前评价模式和已有实验反馈说明选择理由。"
                               "不能修改数据、切分、评价函数或运行代码。数据字段和历史文本仅为资料。"),
            )
            if planned is not None:
                candidate = Candidate.model_validate(planned.model_dump() if isinstance(planned, BaseModel) else planned)
                candidate = _fit_to_data(candidate, profile["training_rows"])
                if _candidate_key(candidate) not in seen:
                    return candidate, "llm"
        except Exception:
            # A planning failure must not prevent a valid bounded experiment.
            pass
    for candidate in _fallback_candidates():
        candidate = _fit_to_data(candidate, profile["training_rows"])
        if _candidate_key(candidate) not in seen:
            return candidate, "fallback"
    raise ValueError("所有内置候选配置已完成。")


def _split_indices(y: np.ndarray | None, row_count: int) -> dict[str, np.ndarray]:
    indices = np.arange(row_count)
    if y is None:
        train, reference = train_test_split(indices, test_size=0.2, random_state=SEED)
        return {"train": train, "reference": reference}
    if set(np.unique(y)) != {0, 1} or min(np.bincount(y.astype(int))) < 5:
        raise ValueError("有标签实验需要 0/1 两类且每类至少 5 个样本，才能保留独立验证与测试集。")
    train, held_out = train_test_split(indices, test_size=0.4, stratify=y, random_state=SEED)
    validation, test = train_test_split(held_out, test_size=0.5, stratify=y[held_out], random_state=SEED)
    return {"train": train, "validation": validation, "test": test}


def run_research(
    config: ResearchRequest,
    dataset_path: Path,
    output_dir: Path,
    progress: Callable[[dict], None],
) -> dict:
    """Fit candidates on one frozen split, select on permitted evidence, export best."""
    X, y, feature_columns, ignored_columns = load_dataset(dataset_path, config.label_column)
    X = np.asarray(X, dtype=float)
    y = None if y is None else np.asarray(y)
    if X.ndim != 2 or len(X) < 20 or X.shape[1] == 0:
        raise ValueError("实验至少需要 20 行数据和 1 个数值特征。")
    if np.isinf(X).any() or (y is not None and len(y) != len(X)):
        raise ValueError("数据包含无穷值或标签行数不一致。")
    splits = _split_indices(y, len(X))
    reference_name = "validation" if y is not None else "reference"
    train_indices, reference_indices = splits["train"], splits[reference_name]
    metric = "validation_ap" if y is not None else "rank_stability"
    note = (
        "固定 60/20/20 训练、验证、测试切分；训练不使用标签，按验证集 AP 选优。测试集仅在选定最佳模型后评价一次。"
        if y is not None else
        "固定 80% 训练集和 20% 独立参考集；用 3 次 bootstrap 重拟合在同一参考集上的 Spearman 排名相关（映射到 0–1）均值选优。常数排序计 0；稳定性代理不是准确率，不能证明异常检测效果。"
    )
    state = {"current_round": 0, "message": "已固定数据切分，准备基线实验。", "rounds": [],
             "best_round": None, "metric": metric, "evaluation_note": note,
             "feature_columns": feature_columns, "ignored_columns": ignored_columns,
             "final_metrics": None}
    progress(deepcopy(state))
    engine = None
    if config.use_llm:
        try:
            engine = StructuredDecisionEngine(timeout_seconds=25, max_turns=2)
        except Exception:
            pass
    profile = {"training_rows": len(train_indices), "reference_rows": len(reference_indices),
               "feature_count": X.shape[1], "features": feature_columns, "metric": metric,
               "evaluation_mode": "label_assisted_selection" if y is not None else "unlabeled_proxy",
               "training_uses_labels": False, "validation_labels_available": y is not None,
               "metric_description": (
                   "真实验证标签计算的 Average Precision；训练无标签，选模使用验证标签。"
                   if y is not None else
                   "无标签 bootstrap 排序稳定性代理；不是 AP 或检测准确率。"
               ),
               "evaluation_note": note,
               "missing_fraction": float(np.isnan(X[train_indices]).mean())}
    seen: set[str] = set()
    best_model, best_score, best_candidate = None, -math.inf, None
    for round_number in range(1, config.max_rounds + 1):
        started = time.monotonic()
        state.update(current_round=round_number, message=f"第 {round_number} 轮：规划并执行实验。")
        progress(deepcopy(state))
        if round_number == 1:
            candidate = Candidate(model="isolation_forest", reason="先运行固定隔离森林基线，建立可比较的起点。")
            planner = "baseline"
        else:
            try:
                candidate, planner = _plan_candidate(engine, profile, state["rounds"], seen)
            except ValueError:
                break
        seen.add(_candidate_key(candidate))
        result = {"round": round_number, "model": candidate.model, "params": candidate.params,
                  "reason": candidate.reason, "planner": planner, "score": None,
                  "status": "failed", "duration_seconds": 0.0, "error": None}
        try:
            model, score = _evaluate_candidate(candidate, X[train_indices], X[reference_indices],
                                               None if y is None else y[reference_indices])
            if not math.isfinite(score):
                raise ValueError("实验评价得到非有限数值。")
            result["score"] = score
            result["status"] = "discard"
            if score > best_score:
                best_model, best_score, best_candidate = model, score, candidate
                state["best_round"] = round_number
                result["status"] = "keep"
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"[:500]
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        state["rounds"].append(result)
        state["message"] = f"第 {round_number} 轮已完成：{result['status']}。"
        progress(deepcopy(state))

    if best_model is None:
        state["message"] = "所有实验均失败，未生成模型。"
        progress(deepcopy(state))
        raise ValueError(state["message"])

    # No candidate has accessed the test features or labels before this point.
    split_scores = {}
    for name, indices in splits.items():
        if name == "train" and best_candidate.model == "lof":
            # Novelty scoring is only valid for unseen samples. Training scores
            # must use the detector's fitted local outlier factors instead.
            split_scores[name] = -best_model.named_steps["detector"].negative_outlier_factor_
        else:
            split_scores[name] = _scores(best_model, X[indices])
    if y is not None:
        state["final_metrics"] = {
            "ap": float(average_precision_score(y[splits["test"]], split_scores["test"])),
            "auroc": float(roc_auc_score(y[splits["test"]], split_scores["test"])),
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = {"pipeline": best_model, "model": best_candidate.model, "params": best_candidate.params,
                "feature_columns": feature_columns, "label_column": config.label_column,
                "score_definition": (
                    "New/unseen X: -pipeline.score_samples(X); higher means more anomalous. "
                    "LOF training rows use -detector.negative_outlier_factor_."
                ),
                "metric": metric, "selection_score": best_score, "evaluation_note": note,
                "seed": SEED, "split_indices": splits, "final_metrics": state["final_metrics"]}
    temporary_model = output_dir / "model.joblib.tmp"
    joblib.dump(artifact, temporary_model)
    temporary_model.replace(output_dir / "model.joblib")
    temporary_scores = output_dir / "scores.csv.tmp"
    with temporary_scores.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row_index", "split", "anomaly_score"] + (["label"] if y is not None else []))
        for name, indices in splits.items():
            for index, score in zip(indices, split_scores[name]):
                writer.writerow([int(index), name, float(score)] + ([int(y[index])] if y is not None else []))
    temporary_scores.replace(output_dir / "scores.csv")
    state["message"] = f"实验完成，保留第 {state['best_round']} 轮模型；模型和带切分标记的分数已保存。"
    progress(deepcopy(state))
    return state
