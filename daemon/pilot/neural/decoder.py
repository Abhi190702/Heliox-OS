"""Transparent SSVEP calibration and inference with JSON-only artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score

from pilot.neural.acquisition import NeuralSampleWindow
from pilot.neural.protocol import (
    ArtifactHash,
    NeuralCalibrationMetricsV1,
    NeuralIntentClass,
    NeuralParadigm,
)
from pilot.neural.quality import SignalQualitySummary

TargetId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{1,64}$")]
DECODER_VERSION = hashlib.sha256(b"heliox-ssvep-cca-logreg-v1").hexdigest()


class NeuralCalibrationError(ValueError):
    """Calibration evidence or its derived artifact failed validation."""


class SSVEPTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    target_id: TargetId
    frequency_hz: float = Field(gt=1, lt=100)
    intent_class: NeuralIntentClass
    command_id: TargetId | None = None

    @model_validator(mode="after")
    def validate_command(self) -> Self:
        if self.intent_class == NeuralIntentClass.SAFE_GOAL and not self.command_id:
            raise ValueError("safe_goal calibration targets require command_id")
        if self.intent_class != NeuralIntentClass.SAFE_GOAL and self.command_id is not None:
            raise ValueError("command_id is valid only for safe_goal targets")
        return self


@dataclass(frozen=True, slots=True)
class CalibrationEpoch:
    window: NeuralSampleWindow
    target_id: str
    block_id: str


CalibrationMetrics = NeuralCalibrationMetricsV1


class SSVEPCalibrationArtifact(BaseModel):
    """Portable inference weights; raw neural samples are never serialized."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: int = Field(default=1, ge=1, le=1)
    calibration_id: ArtifactHash
    decoder_version: ArtifactHash
    subject_key: TargetId
    paradigm: NeuralParadigm = NeuralParadigm.SSVEP
    sample_rate_hz: int = Field(ge=1, le=4096)
    channel_names: tuple[str, ...] = Field(min_length=1, max_length=64)
    reference: str = Field(min_length=1, max_length=256)
    window_samples: int = Field(ge=64, le=131072)
    harmonics: int = Field(ge=1, le=5)
    targets: tuple[SSVEPTarget, ...] = Field(min_length=2, max_length=16)
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    class_order: tuple[TargetId, ...]
    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    metrics: CalibrationMetrics

    @model_validator(mode="after")
    def validate_shapes(self) -> Self:
        feature_count = len(self.targets)
        class_count = len(self.class_order)
        if len({target.target_id for target in self.targets}) != feature_count:
            raise ValueError("target_id values must be unique")
        frequencies = [round(target.frequency_hz, 6) for target in self.targets]
        if len(set(frequencies)) != feature_count:
            raise ValueError("SSVEP frequencies must be unique")
        if set(self.class_order) != {target.target_id for target in self.targets}:
            raise ValueError("class_order must cover every target exactly once")
        if len(self.feature_mean) != feature_count or len(self.feature_scale) != feature_count:
            raise ValueError("feature normalization shape is invalid")
        expected_rows = 1 if class_count == 2 else class_count
        if len(self.coefficients) != expected_rows or len(self.intercepts) != expected_rows:
            raise ValueError("classifier output shape is invalid")
        if any(len(row) != feature_count for row in self.coefficients):
            raise ValueError("classifier feature shape is invalid")
        if any(value <= 0 for value in self.feature_scale):
            raise ValueError("feature scales must be positive")
        return self

    def content_payload(self) -> bytes:
        data = self.model_dump(mode="json", exclude={"calibration_id"})
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

    def verify_content_hash(self) -> None:
        actual = hashlib.sha256(self.content_payload()).hexdigest()
        if actual != self.calibration_id:
            raise NeuralCalibrationError("calibration artifact content hash does not match")

    def save(self, path: Path) -> None:
        self.verify_content_hash()
        destination = path.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = self.model_dump_json(indent=2, by_alias=True)
        handle, temporary = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, text=True
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise

    @classmethod
    def load(cls, path: Path) -> SSVEPCalibrationArtifact:
        try:
            artifact = cls.model_validate_json(path.expanduser().resolve().read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise NeuralCalibrationError(f"invalid calibration artifact: {exc}") from exc
        artifact.verify_content_hash()
        return artifact


@dataclass(frozen=True, slots=True)
class DecodedNeuralCandidate:
    target_id: str
    intent_class: NeuralIntentClass
    command_id: str | None
    posterior_permille: int
    margin_permille: int
    probabilities: tuple[tuple[str, float], ...]
    quality: SignalQualitySummary


def _inverse_sqrt(matrix: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(matrix)
    floor = max(float(np.max(values)) * 1e-8, np.finfo(np.float64).eps)
    return (vectors * (1.0 / np.sqrt(np.maximum(values, floor)))) @ vectors.T


def _ssvep_features(
    window: NeuralSampleWindow,
    *,
    sample_rate_hz: int,
    frequencies_hz: tuple[float, ...],
    harmonics: int,
) -> np.ndarray:
    """Return regularized first canonical correlation for each target."""

    data = window.samples_uv.T - np.mean(window.samples_uv.T, axis=0, keepdims=True)
    channel_scale = np.std(data, axis=0, keepdims=True)
    data = data / np.maximum(channel_scale, np.finfo(np.float64).eps)
    covariance_x = data.T @ data / max(window.sample_count - 1, 1)
    covariance_x += np.eye(covariance_x.shape[0]) * 1e-6
    whitening_x = _inverse_sqrt(covariance_x)
    seconds = np.arange(window.sample_count, dtype=np.float64) / sample_rate_hz
    features: list[float] = []
    for frequency in frequencies_hz:
        references = []
        for harmonic in range(1, harmonics + 1):
            angle = 2 * np.pi * frequency * harmonic * seconds
            references.extend((np.sin(angle), np.cos(angle)))
        basis = np.stack(references).T
        basis -= np.mean(basis, axis=0, keepdims=True)
        basis /= np.maximum(np.std(basis, axis=0, keepdims=True), np.finfo(np.float64).eps)
        covariance_y = basis.T @ basis / max(window.sample_count - 1, 1)
        covariance_y += np.eye(covariance_y.shape[0]) * 1e-6
        cross = data.T @ basis / max(window.sample_count - 1, 1)
        canonical = whitening_x @ cross @ _inverse_sqrt(covariance_y)
        first_correlation = float(np.linalg.svd(canonical, compute_uv=False)[0])
        features.append(float(np.clip(first_correlation, 0, 1)))
    return np.asarray(features, dtype=np.float64)


def _expected_calibration_error(probabilities: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    confidence = np.max(probabilities, axis=1)
    predictions = np.argmax(probabilities, axis=1)
    total = max(len(labels), 1)
    error = 0.0
    for lower in np.linspace(0, 1, bins, endpoint=False):
        upper = lower + 1 / bins
        members = (confidence > lower) & (confidence <= upper)
        if not np.any(members):
            continue
        accuracy = float(np.mean(predictions[members] == labels[members]))
        error += float(np.sum(members)) / total * abs(accuracy - float(np.mean(confidence[members])))
    return error


class SSVEPCalibrator:
    def __init__(
        self,
        *,
        targets: tuple[SSVEPTarget, ...],
        harmonics: int = 2,
        minimum_balanced_accuracy: float = 0.65,
        minimum_per_class_recall: float = 0.50,
        maximum_expected_calibration_error: float = 0.25,
        minimum_chance_advantage: float = 0.10,
    ) -> None:
        if not 1 <= harmonics <= 5:
            raise ValueError("harmonics must be between one and five")
        if len(targets) < 2:
            raise ValueError("at least two SSVEP targets are required")
        if not 0 <= minimum_balanced_accuracy <= 1:
            raise ValueError("minimum_balanced_accuracy must be between zero and one")
        if not 0 <= minimum_per_class_recall <= 1:
            raise ValueError("minimum_per_class_recall must be between zero and one")
        if not 0 <= maximum_expected_calibration_error <= 1:
            raise ValueError("maximum_expected_calibration_error must be between zero and one")
        if not 0 <= minimum_chance_advantage <= 1:
            raise ValueError("minimum_chance_advantage must be between zero and one")
        self._targets = targets
        self._harmonics = harmonics
        self._minimum_balanced_accuracy = minimum_balanced_accuracy
        self._minimum_per_class_recall = minimum_per_class_recall
        self._maximum_expected_calibration_error = maximum_expected_calibration_error
        self._minimum_chance_advantage = minimum_chance_advantage

    def _validate_metrics(self, metrics: CalibrationMetrics) -> None:
        chance_floor = (1.0 / len(self._targets)) + self._minimum_chance_advantage
        required_accuracy = max(self._minimum_balanced_accuracy, chance_floor)
        if metrics.balanced_accuracy < required_accuracy:
            raise NeuralCalibrationError("held-block balanced accuracy is below the registered calibration threshold")
        if min(metrics.per_class_recall.values(), default=0.0) < self._minimum_per_class_recall:
            raise NeuralCalibrationError("held-block per-class recall indicates a collapsed target")
        if metrics.expected_calibration_error > self._maximum_expected_calibration_error:
            raise NeuralCalibrationError("held-block probabilities are not sufficiently calibrated")

    def fit(
        self,
        epochs: list[CalibrationEpoch],
        *,
        subject_key: str,
        sample_rate_hz: int,
        channel_names: tuple[str, ...],
        reference: str,
    ) -> SSVEPCalibrationArtifact:
        target_ids = tuple(target.target_id for target in self._targets)
        frequencies = tuple(target.frequency_hz for target in self._targets)
        if len(set(target_ids)) != len(target_ids):
            raise NeuralCalibrationError("calibration targets must have unique identifiers")
        if len(set(frequencies)) != len(frequencies):
            raise NeuralCalibrationError("calibration targets must have unique frequencies")
        if max(frequencies) * self._harmonics >= sample_rate_hz / 2:
            raise NeuralCalibrationError("SSVEP target harmonics must remain below Nyquist")
        if any(epoch.target_id not in target_ids for epoch in epochs):
            raise NeuralCalibrationError("epoch label is not a registered target")
        blocks = sorted({epoch.block_id for epoch in epochs})
        if len(blocks) < 2:
            raise NeuralCalibrationError("at least two complete calibration blocks are required")
        per_target = {target_id: 0 for target_id in target_ids}
        per_block = {block: set() for block in blocks}
        window_sizes = {epoch.window.sample_count for epoch in epochs}
        if len(window_sizes) != 1:
            raise NeuralCalibrationError("all calibration epochs must use one registered window length")
        window_samples = next(iter(window_sizes), 0)
        if window_samples < sample_rate_hz:
            raise NeuralCalibrationError("SSVEP calibration windows must be at least one second")
        for epoch in epochs:
            if epoch.window.channel_count != len(channel_names):
                raise NeuralCalibrationError("epoch channel count changed during calibration")
            per_target[epoch.target_id] += 1
            per_block[epoch.block_id].add(epoch.target_id)
        if min(per_target.values(), default=0) < 2:
            raise NeuralCalibrationError("every target requires at least two epochs")
        if any(labels != set(target_ids) for labels in per_block.values()):
            raise NeuralCalibrationError("every calibration block must contain every target")

        features = np.stack(
            [
                _ssvep_features(
                    epoch.window,
                    sample_rate_hz=sample_rate_hz,
                    frequencies_hz=frequencies,
                    harmonics=self._harmonics,
                )
                for epoch in epochs
            ]
        )
        labels = np.asarray([target_ids.index(epoch.target_id) for epoch in epochs], dtype=int)
        block_ids = np.asarray([epoch.block_id for epoch in epochs])
        held_probabilities = np.zeros((len(epochs), len(target_ids)), dtype=np.float64)
        for held_block in blocks:
            train = block_ids != held_block
            test = ~train
            model, mean, scale = self._fit_classifier(features[train], labels[train])
            fold = model.predict_proba((features[test] - mean) / scale)
            held_probabilities[test] = self._align_probabilities(fold, model.classes_, len(target_ids))
        predictions = np.argmax(held_probabilities, axis=1)
        recalls = {
            target_id: float(np.mean(predictions[labels == index] == index))
            for index, target_id in enumerate(target_ids)
        }
        metrics = CalibrationMetrics(
            epoch_count=len(epochs),
            block_count=len(blocks),
            balanced_accuracy=float(balanced_accuracy_score(labels, predictions)),
            expected_calibration_error=_expected_calibration_error(held_probabilities, labels),
            per_class_recall=recalls,
        )
        self._validate_metrics(metrics)
        model, mean, scale = self._fit_classifier(features, labels)
        coefficients = tuple(tuple(float(value) for value in row) for row in model.coef_)
        base = SSVEPCalibrationArtifact(
            calibration_id="0" * 64,
            decoder_version=DECODER_VERSION,
            subject_key=subject_key,
            sample_rate_hz=sample_rate_hz,
            channel_names=channel_names,
            reference=reference,
            window_samples=window_samples,
            harmonics=self._harmonics,
            targets=self._targets,
            feature_mean=tuple(float(value) for value in mean),
            feature_scale=tuple(float(value) for value in scale),
            class_order=target_ids,
            coefficients=coefficients,
            intercepts=tuple(float(value) for value in model.intercept_),
            metrics=metrics,
        )
        calibration_id = hashlib.sha256(base.content_payload()).hexdigest()
        artifact = base.model_copy(update={"calibration_id": calibration_id})
        artifact.verify_content_hash()
        return artifact

    @staticmethod
    def _fit_classifier(features: np.ndarray, labels: np.ndarray) -> tuple[LogisticRegression, np.ndarray, np.ndarray]:
        mean = np.mean(features, axis=0)
        scale = np.std(features, axis=0)
        scale = np.where(scale < 1e-9, 1.0, scale)
        model = LogisticRegression(C=1.0, max_iter=1000, random_state=0)
        model.fit((features - mean) / scale, labels)
        return model, mean, scale

    @staticmethod
    def _align_probabilities(probabilities: np.ndarray, classes: np.ndarray, class_count: int) -> np.ndarray:
        aligned = np.zeros((probabilities.shape[0], class_count), dtype=np.float64)
        aligned[:, classes.astype(int)] = probabilities
        return aligned


class SSVEPDecoder:
    def __init__(self, artifact: SSVEPCalibrationArtifact) -> None:
        artifact.verify_content_hash()
        if artifact.decoder_version != DECODER_VERSION:
            raise NeuralCalibrationError("calibration artifact uses an unsupported decoder")
        self.artifact = artifact
        self._targets = {target.target_id: target for target in artifact.targets}

    def decode(self, window: NeuralSampleWindow, *, quality: SignalQualitySummary) -> DecodedNeuralCandidate:
        if window.channel_count != len(self.artifact.channel_names):
            raise NeuralCalibrationError("inference channel count does not match calibration")
        if window.sample_count != self.artifact.window_samples:
            raise NeuralCalibrationError("inference window length does not match calibration")
        frequencies = tuple(target.frequency_hz for target in self.artifact.targets)
        features = _ssvep_features(
            window,
            sample_rate_hz=self.artifact.sample_rate_hz,
            frequencies_hz=frequencies,
            harmonics=self.artifact.harmonics,
        )
        normalized = (features - np.asarray(self.artifact.feature_mean)) / np.asarray(self.artifact.feature_scale)
        coefficients = np.asarray(self.artifact.coefficients)
        intercepts = np.asarray(self.artifact.intercepts)
        logits = coefficients @ normalized + intercepts
        if len(self.artifact.class_order) == 2 and logits.shape == (1,):
            # sklearn's binary logistic probability is softmax([0, z]), not
            # softmax([-z, z]); the latter would double confidence.
            logits = np.array([0.0, logits[0]])
        probabilities = np.exp(logits - np.max(logits))
        probabilities /= np.sum(probabilities)
        order = np.argsort(probabilities)[::-1]
        top, second = int(order[0]), int(order[1])
        target_id = self.artifact.class_order[top]
        target = self._targets[target_id]
        return DecodedNeuralCandidate(
            target_id=target_id,
            intent_class=target.intent_class,
            command_id=target.command_id,
            posterior_permille=int(round(probabilities[top] * 1000)),
            margin_permille=int(round((probabilities[top] - probabilities[second]) * 1000)),
            probabilities=tuple(
                (self.artifact.class_order[index], round(float(probabilities[index]), 6))
                for index in range(len(probabilities))
            ),
            quality=quality,
        )
