from __future__ import annotations

from pilot.neural.acquisition import SyntheticNeuralSource
from pilot.neural.decoder import SSVEPDecoder
from pilot.neural.gate import NeuralIntentSigner
from pilot.neural.protocol import NeuralScope
from pilot.neural.service import NeuralDecoderService
from pilot.neural.simulator import build_synthetic_calibration_artifact


def test_one_hour_synthetic_no_control_soak_emits_zero_intents() -> None:
    """Registered deterministic N2 negative: noise must always abstain."""

    artifact = build_synthetic_calibration_artifact()
    service = NeuralDecoderService(
        source=SyntheticNeuralSource(target_hz=None, noise_uv=1.5, seed=90210),
        decoder=SSVEPDecoder(artifact),
        signer=NeuralIntentSigner(b"s" * 32),
    )
    step_seconds = 0.5
    observation_count = round(60 * 60 / step_seconds)
    intents = []
    service.start()
    try:
        for _ in range(observation_count):
            observation = service.observe_once(
                state_revision=1,
                requested_scope=NeuralScope.NAVIGATE,
            )
            if observation.intent is not None:
                intents.append(observation.intent)
    finally:
        service.stop()

    assert observation_count * step_seconds == 3600
    assert intents == []
