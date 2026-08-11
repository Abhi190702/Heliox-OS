"""Neural-intent contracts and fail-closed session authority.

Raw EEG never belongs in this package's planner-facing API. Acquisition and
decoding produce a bounded :class:`NeuralIntentV1`; the gate below decides
whether that evidence may preview one pre-authorized goal.
"""

from pilot.neural.acquisition import (
    BoundedNeuralBuffer,
    BrainFlowNeuralSource,
    LSLNeuralSource,
    NeuralAcquisitionError,
    NeuralBufferHealth,
    NeuralSampleWindow,
    NeuralSource,
    PlaybackNeuralSource,
    SyntheticNeuralSource,
)
from pilot.neural.controller import NeuralControlError, NeuralController
from pilot.neural.decoder import (
    CalibrationEpoch,
    CalibrationMetrics,
    DecodedNeuralCandidate,
    NeuralCalibrationError,
    SSVEPCalibrationArtifact,
    SSVEPCalibrator,
    SSVEPDecoder,
    SSVEPTarget,
)
from pilot.neural.gate import (
    NeuralIntentGate,
    NeuralIntentGateConfig,
    NeuralIntentSigner,
    NeuralSessionState,
)
from pilot.neural.goals import (
    NeuralGoalDefinition,
    NeuralGoalError,
    NeuralGoalRegistry,
    default_neural_goals,
)
from pilot.neural.protocol import (
    ArtifactFlag,
    NeuralCalibrationMetricsV1,
    NeuralIntentClass,
    NeuralIntentV1,
    NeuralParadigm,
    NeuralScope,
    NeuralStreamDescriptorV1,
    SignalQuality,
)
from pilot.neural.quality import (
    NeuralSignalQualityAnalyzer,
    SignalQualityConfig,
    SignalQualitySummary,
)
from pilot.neural.service import NeuralDecoderService, NeuralObservation

__all__ = [
    "ArtifactFlag",
    "BoundedNeuralBuffer",
    "BrainFlowNeuralSource",
    "CalibrationEpoch",
    "CalibrationMetrics",
    "DecodedNeuralCandidate",
    "LSLNeuralSource",
    "NeuralAcquisitionError",
    "NeuralBufferHealth",
    "NeuralCalibrationError",
    "NeuralCalibrationMetricsV1",
    "NeuralControlError",
    "NeuralController",
    "NeuralDecoderService",
    "NeuralIntentClass",
    "NeuralIntentGate",
    "NeuralIntentGateConfig",
    "NeuralIntentSigner",
    "NeuralIntentV1",
    "NeuralGoalDefinition",
    "NeuralGoalError",
    "NeuralGoalRegistry",
    "NeuralParadigm",
    "NeuralScope",
    "NeuralObservation",
    "NeuralSampleWindow",
    "NeuralSessionState",
    "NeuralSource",
    "NeuralStreamDescriptorV1",
    "SignalQuality",
    "SignalQualityConfig",
    "SignalQualitySummary",
    "NeuralSignalQualityAnalyzer",
    "PlaybackNeuralSource",
    "SyntheticNeuralSource",
    "default_neural_goals",
    "SSVEPCalibrationArtifact",
    "SSVEPCalibrator",
    "SSVEPDecoder",
    "SSVEPTarget",
]
