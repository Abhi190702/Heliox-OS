"""Inspect neural signal health before decoding or emitting an intent."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import signal

from pilot.neural.acquisition import NeuralSampleWindow
from pilot.neural.protocol import ArtifactFlag, SignalQuality


@dataclass(frozen=True, slots=True)
class SignalQualityConfig:
    saturation_uv: float = 500.0
    flat_std_uv: float = 0.25
    blink_peak_uv: float = 180.0
    line_noise_ratio: float = 0.35
    muscle_ratio: float = 0.45
    max_gap_factor: float = 1.8
    max_jitter_ratio: float = 0.35
    minimum_samples: int = 64

    def __post_init__(self) -> None:
        if (
            min(
                self.saturation_uv,
                self.flat_std_uv,
                self.blink_peak_uv,
                self.max_gap_factor,
                self.minimum_samples,
            )
            <= 0
        ):
            raise ValueError("signal-quality limits must be positive")
        if not 0 < self.line_noise_ratio < 1 or not 0 < self.muscle_ratio < 1:
            raise ValueError("spectral artifact limits must be ratios")
        if not 0 < self.max_jitter_ratio < 1:
            raise ValueError("max_jitter_ratio must be between zero and one")


class SignalQualitySummary(BaseModel):
    """Bounded derived metadata; safe to send outside the neural sidecar."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    quality: SignalQuality
    artifact_flags: tuple[ArtifactFlag, ...] = ()
    channel_std_uv: tuple[float, ...] = Field(max_length=64)
    line_noise_ratio: float = Field(ge=0, le=1)
    muscle_ratio: float = Field(ge=0, le=1)
    estimated_missing_samples: int = Field(ge=0)
    timestamp_jitter_ratio: float = Field(ge=0)
    reasons: tuple[str, ...] = Field(max_length=16)


class NeuralSignalQualityAnalyzer:
    def __init__(self, config: SignalQualityConfig | None = None) -> None:
        self._config = config or SignalQualityConfig()

    def analyze(
        self,
        window: NeuralSampleWindow,
        *,
        sample_rate_hz: int,
        channel_names: tuple[str, ...],
    ) -> SignalQualitySummary:
        if window.channel_count != len(channel_names):
            raise ValueError("channel metadata does not match the sample window")
        if window.sample_count < self._config.minimum_samples:
            return SignalQualitySummary(
                quality=SignalQuality.REJECT,
                artifact_flags=(ArtifactFlag.PACKET_LOSS,),
                channel_std_uv=tuple(float(value) for value in np.std(window.samples_uv, axis=1)),
                line_noise_ratio=0,
                muscle_ratio=0,
                estimated_missing_samples=self._config.minimum_samples - window.sample_count,
                timestamp_jitter_ratio=0,
                reasons=("insufficient_samples",),
            )

        samples = signal.detrend(window.samples_uv, axis=1, type="linear")
        std_values = np.std(samples, axis=1)
        flags: set[ArtifactFlag] = set()
        reasons: list[str] = []

        if np.any(std_values < self._config.flat_std_uv):
            flags.add(ArtifactFlag.FLAT_CHANNEL)
            reasons.append("flat_channel")
        if np.any(np.abs(window.samples_uv) >= self._config.saturation_uv):
            flags.add(ArtifactFlag.SATURATION)
            reasons.append("amplitude_saturation")

        frequencies = np.fft.rfftfreq(window.sample_count, d=1 / sample_rate_hz)
        power = np.abs(np.fft.rfft(samples, axis=1)) ** 2
        physiological = (frequencies >= 1.0) & (frequencies <= min(100.0, sample_rate_hz / 2))
        total_power = float(np.sum(power[:, physiological])) + np.finfo(np.float64).eps
        line_mask = ((frequencies >= 49) & (frequencies <= 51)) | ((frequencies >= 59) & (frequencies <= 61))
        line_ratio = float(np.clip(np.sum(power[:, line_mask]) / total_power, 0, 1))
        muscle_mask = (frequencies >= 30) & (frequencies <= min(100.0, sample_rate_hz / 2))
        muscle_ratio = float(np.clip(np.sum(power[:, muscle_mask]) / total_power, 0, 1))
        if line_ratio >= self._config.line_noise_ratio:
            flags.add(ArtifactFlag.LINE_NOISE)
            reasons.append("line_noise")
        if muscle_ratio >= self._config.muscle_ratio:
            flags.add(ArtifactFlag.MUSCLE)
            reasons.append("high_frequency_muscle")

        frontal = [index for index, name in enumerate(channel_names) if name.casefold().startswith(("fp", "af", "eog"))]
        if frontal and np.max(np.abs(samples[frontal])) >= self._config.blink_peak_uv:
            flags.add(ArtifactFlag.BLINK)
            reasons.append("frontal_blink_peak")

        intervals = np.diff(window.timestamps_ns).astype(np.float64)
        nominal = 1_000_000_000 / sample_rate_hz
        missing = int(np.sum(np.maximum(np.rint(intervals / nominal).astype(int) - 1, 0)))
        if missing or window.dropped_before:
            flags.add(ArtifactFlag.PACKET_LOSS)
            reasons.append("sample_gap")
            missing += window.dropped_before
        median_interval = float(np.median(intervals))
        jitter = float(np.median(np.abs(intervals - median_interval)) / nominal)
        if np.max(intervals) > nominal * self._config.max_gap_factor or jitter > self._config.max_jitter_ratio:
            flags.add(ArtifactFlag.CLOCK)
            reasons.append("clock_jitter")

        severe = {
            ArtifactFlag.SATURATION,
            ArtifactFlag.FLAT_CHANNEL,
            ArtifactFlag.PACKET_LOSS,
            ArtifactFlag.CLOCK,
        }
        quality = SignalQuality.REJECT if flags & severe else SignalQuality.DEGRADED if flags else SignalQuality.GOOD
        ordered_flags = tuple(sorted(flags, key=lambda flag: flag.value))
        return SignalQualitySummary(
            quality=quality,
            artifact_flags=ordered_flags,
            channel_std_uv=tuple(round(float(value), 6) for value in std_values),
            line_noise_ratio=round(line_ratio, 6),
            muscle_ratio=round(muscle_ratio, 6),
            estimated_missing_samples=missing,
            timestamp_jitter_ratio=round(jitter, 6),
            reasons=tuple(reasons),
        )
