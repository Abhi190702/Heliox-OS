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
from pilot.neural.gate import (
    NeuralIntentGate,
    NeuralIntentGateConfig,
    NeuralIntentSigner,
    NeuralSessionState,
)
from pilot.neural.protocol import (
    ArtifactFlag,
    NeuralIntentClass,
    NeuralIntentV1,
    NeuralParadigm,
    NeuralScope,
    NeuralStreamDescriptorV1,
    SignalQuality,
)

__all__ = [
    "ArtifactFlag",
    "BoundedNeuralBuffer",
    "BrainFlowNeuralSource",
    "LSLNeuralSource",
    "NeuralAcquisitionError",
    "NeuralBufferHealth",
    "NeuralIntentClass",
    "NeuralIntentGate",
    "NeuralIntentGateConfig",
    "NeuralIntentSigner",
    "NeuralIntentV1",
    "NeuralParadigm",
    "NeuralScope",
    "NeuralSampleWindow",
    "NeuralSessionState",
    "NeuralSource",
    "NeuralStreamDescriptorV1",
    "SignalQuality",
    "PlaybackNeuralSource",
    "SyntheticNeuralSource",
]
