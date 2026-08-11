"""Neural-intent contracts and fail-closed session authority.

Raw EEG never belongs in this package's planner-facing API. Acquisition and
decoding produce a bounded :class:`NeuralIntentV1`; the gate below decides
whether that evidence may preview one pre-authorized goal.
"""

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
    "NeuralIntentClass",
    "NeuralIntentGate",
    "NeuralIntentGateConfig",
    "NeuralIntentSigner",
    "NeuralIntentV1",
    "NeuralParadigm",
    "NeuralScope",
    "NeuralSessionState",
    "NeuralStreamDescriptorV1",
    "SignalQuality",
]
