"""Deterministic in-process inference stub.

A real deployment would load a pickled scikit-learn / PyTorch / LightGBM artifact
from `artifact_uri`. For this regulated-offline workbench we need deterministic
outputs the tests can assert against, so we compute the score from the features
themselves using the model's `artifact_params` as weights:

    score = sigmoid( bias + sum(weight_i * feature_i) )

If a feature is missing from the input, 0 is substituted. Missing params default
to zero weight.
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass
from typing import Mapping

from app.services import metrics


@dataclass
class PredictResult:
    subject_key: str
    experiment_id: str
    arm: str
    model_version_id: str
    score: float
    latency_ms: float


# Process-local artifact cache; the plan calls for pre-warmed artifacts.
_artifact_cache: dict[str, dict] = {}


def warm(model_version_id: str, artifact_params: dict) -> None:
    _artifact_cache[model_version_id] = artifact_params or {}


def _params_for(model_version_id: str, fallback: dict | None = None) -> dict:
    params = _artifact_cache.get(model_version_id)
    if params is None and fallback is not None:
        _artifact_cache[model_version_id] = fallback
        params = fallback
    return params or {}


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def predict(
    *,
    subject_key: str,
    experiment_id: uuid.UUID | str,
    model_version_id: uuid.UUID | str,
    artifact_params: Mapping[str, float],
    features: Mapping[str, float],
    arm: str,
) -> PredictResult:
    metrics.inc_request()
    start = time.perf_counter()
    params = _params_for(str(model_version_id), dict(artifact_params))
    bias = float(params.get("bias", 0.0))
    total = bias
    for name, weight in params.get("weights", {}).items():
        val = features.get(name, 0)
        try:
            total += float(weight) * float(val)
        except (TypeError, ValueError):
            pass
    score = _sigmoid(total)
    latency_ms = (time.perf_counter() - start) * 1000
    metrics.record_inference_latency_ms(latency_ms)
    return PredictResult(
        subject_key=subject_key,
        experiment_id=str(experiment_id),
        arm=arm,
        model_version_id=str(model_version_id),
        score=score,
        latency_ms=round(latency_ms, 4),
    )
