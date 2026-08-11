"""Runnable neurod-to-Heliox paired WebSocket bridge."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from websockets.asyncio.client import ClientConnection, connect

from pilot.config import DATA_DIR, RUNTIME_DIR
from pilot.neural.acquisition import (
    BrainFlowNeuralSource,
    LSLNeuralSource,
    PlaybackNeuralSource,
    SyntheticNeuralSource,
)
from pilot.neural.decoder import SSVEPCalibrationArtifact, SSVEPDecoder
from pilot.neural.gate import NeuralIntentSigner
from pilot.neural.protocol import NeuralScope, NeuralStimulusMarkerV1
from pilot.neural.recording import (
    EncryptedNeuralRecorder,
    NeuralRecordingConsentV1,
    prune_expired_neural_recordings,
)
from pilot.neural.service import NeuralDecoderService
from pilot.neural.simulator import ensure_synthetic_calibration_artifact
from pilot.security.rpc_identity import derive_neural_signing_key

logger = logging.getLogger("pilot.neural.rpc_client")


class NeuralRpcError(RuntimeError):
    pass


class NeuralRpcTransport:
    """Sequential JSON-RPC transport; neurod is excluded from UI broadcasts."""

    def __init__(self, *, url: str, token: str, timeout_seconds: float = 10.0) -> None:
        self._url = url
        self._token = token
        self._timeout = timeout_seconds
        self._connection: ClientConnection | None = None
        self._request_id = 0

    async def connect(self) -> None:
        if self._connection is not None:
            return
        self._connection = await connect(
            self._url,
            open_timeout=self._timeout,
            ping_interval=30,
            ping_timeout=30,
        )
        result = await self.call("auth", {"token": self._token})
        if result.get("role") != "neural_sidecar":
            await self.close()
            raise NeuralRpcError("daemon did not grant the neural_sidecar role")

    async def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            await connection.close()

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._connection is None:
            raise NeuralRpcError("neural RPC transport is not connected")
        self._request_id += 1
        request_id = f"neurod-{self._request_id}"
        await self._connection.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or {},
                    "id": request_id,
                },
                separators=(",", ":"),
            )
        )
        try:
            raw = await asyncio.wait_for(self._connection.recv(), timeout=self._timeout)
        except TimeoutError as exc:
            raise NeuralRpcError(f"RPC timed out: {method}") from exc
        response = json.loads(str(raw))
        if response.get("id") != request_id:
            raise NeuralRpcError("neural RPC response id did not match")
        if "error" in response:
            raise NeuralRpcError(str(response["error"].get("message") or "RPC failed"))
        result = response.get("result")
        if not isinstance(result, dict):
            raise NeuralRpcError("neural RPC returned a non-object result")
        return result


class BridgeTransport(Protocol):
    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...


class NeurodBridge:
    """Pair acquisition with Heliox while keeping raw samples process-local."""

    _ARMED_STATES = {"armed_safe_ui", "armed_safe_desktop"}

    def __init__(
        self,
        *,
        transport: BridgeTransport,
        service: NeuralDecoderService,
        artifact: SSVEPCalibrationArtifact,
        poll_seconds: float = 0.5,
    ) -> None:
        if not 0.05 <= poll_seconds <= 5:
            raise ValueError("neurod poll interval must be between 50 ms and 5 seconds")
        self._transport = transport
        self._service = service
        self._artifact = artifact
        self._poll_seconds = poll_seconds
        self._activated_revision = -1
        self._last_marker_sequence = -1

    async def run(self, stop_event: asyncio.Event | None = None) -> None:
        stop = stop_event or asyncio.Event()
        self._service.start()
        try:
            await self._transport.connect()
            connected = await self._transport.call(
                "neural_connect",
                {"descriptor": self._service.descriptor.model_dump(mode="json")},
            )
            self._require_ok(connected, "connect")
            while not stop.is_set():
                marker_result = await self._transport.call(
                    "neural_stimulus_markers",
                    {"after_sequence": self._last_marker_sequence},
                )
                self._require_ok(marker_result, "stimulus marker sync")
                for payload in marker_result.get("markers", []):
                    marker = NeuralStimulusMarkerV1.model_validate(payload)
                    self._service.record_stimulus_marker(marker)
                    self._last_marker_sequence = marker.sequence
                status = await self._transport.call("neural_status")
                state = str(status.get("state") or "")
                revision = int(status.get("state_revision", 0))
                if state == "calibrating" and revision != self._activated_revision:
                    result = await self._transport.call(
                        "neural_finish_calibration",
                        {
                            "session_id": str(self._service.descriptor.session_id),
                            "calibration_id": self._artifact.calibration_id,
                            "decoder_version": self._artifact.decoder_version,
                            "subject_key": self._artifact.subject_key,
                            "metrics": self._artifact.metrics.model_dump(mode="json"),
                        },
                    )
                    self._require_ok(result, "calibration activation")
                    self._activated_revision = revision
                elif state in self._ARMED_STATES:
                    scope = NeuralScope.NAVIGATE if state == "armed_safe_ui" else NeuralScope.SAFE_DESKTOP
                    observation = self._service.observe_once(
                        state_revision=revision,
                        requested_scope=scope,
                    )
                    health = self._service.buffer_health
                    telemetry = await self._transport.call(
                        "neural_observation",
                        {
                            "quality": observation.quality.model_dump(mode="json"),
                            "buffered_samples": health.buffered_samples,
                            "dropped_samples": health.dropped_samples,
                            "observed_at_ns": time.monotonic_ns(),
                        },
                    )
                    self._require_ok(telemetry, "quality telemetry")
                    if observation.intent is not None:
                        preview = await self._transport.call(
                            "neural_intent_preview",
                            {"intent": observation.intent.model_dump(mode="json", by_alias=True)},
                        )
                        # Low dwell/margin/confidence is a normal abstention,
                        # not a retryable delivery error.
                        if preview.get("status") not in {"previewed", "cancelled", "rejected"}:
                            raise NeuralRpcError("daemon returned an invalid preview state")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=self._poll_seconds)
                except TimeoutError:
                    pass
        finally:
            self._service.stop()
            await self._transport.close()

    @staticmethod
    def _require_ok(result: dict[str, Any], operation: str) -> None:
        if result.get("status") != "ok":
            raise NeuralRpcError(f"neural {operation} rejected: {result.get('error', 'unknown error')}")


def _source_from_args(args: argparse.Namespace, artifact: SSVEPCalibrationArtifact):
    if args.source == "synthetic":
        return SyntheticNeuralSource(
            sample_rate_hz=artifact.sample_rate_hz,
            channel_names=artifact.channel_names,
            target_hz=args.synthetic_frequency,
            seed=args.seed,
        )
    if args.source == "playback":
        if not args.playback:
            raise ValueError("--playback is required for playback source")
        return PlaybackNeuralSource.from_npz(Path(args.playback))
    if args.source == "brainflow":
        parameters = {"serial_port": args.serial_port} if args.serial_port else {}
        return BrainFlowNeuralSource(
            board_id=args.board_id,
            channel_names=artifact.channel_names,
            reference=artifact.reference,
            input_parameters=parameters,
        )
    return LSLNeuralSource(
        stream_name=args.lsl_name,
        channel_names=artifact.channel_names,
        sample_rate_hz=artifact.sample_rate_hz,
        reference=artifact.reference,
    )


async def _run_from_args(args: argparse.Namespace) -> None:
    token = Path(args.token_file).expanduser().resolve().read_text(encoding="utf-8").strip()
    if args.artifact:
        artifact = SSVEPCalibrationArtifact.load(Path(args.artifact))
    elif args.source == "synthetic":
        artifact = ensure_synthetic_calibration_artifact(RUNTIME_DIR / "synthetic_ssvep_calibration.json")
    else:
        raise ValueError("--artifact is required for live and playback neural sources")
    source = _source_from_args(args, artifact)
    signer = NeuralIntentSigner(derive_neural_signing_key(token))
    recorder_factory = None
    if args.record_raw:
        granted_at = datetime.now(UTC)
        recording_path = (
            Path(args.recording_file)
            if args.recording_file
            else DATA_DIR / "neural" / f"{artifact.subject_key}-{granted_at:%Y%m%dT%H%M%SZ}.neeg"
        )
        prune_expired_neural_recordings(recording_path.expanduser().resolve().parent)

        def recorder_factory(descriptor):
            consent = NeuralRecordingConsentV1(
                session_id=descriptor.session_id,
                subject_key=artifact.subject_key,
                purpose=args.recording_purpose,
                granted_at=granted_at,
                expires_at=granted_at + timedelta(days=args.retention_days),
                retention_days=args.retention_days,
                allow_bids_export=args.allow_bids_export,
                authorized=True,
            )
            return EncryptedNeuralRecorder(
                destination=recording_path,
                descriptor=descriptor,
                consent=consent,
            )

    service = NeuralDecoderService(
        source=source,
        decoder=SSVEPDecoder(artifact),
        signer=signer,
        recorder_factory=recorder_factory,
    )
    bridge = NeurodBridge(
        transport=NeuralRpcTransport(url=args.url, token=token),
        service=service,
        artifact=artifact,
        poll_seconds=args.poll_seconds,
    )
    await bridge.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Heliox least-privileged neural gateway")
    parser.add_argument("--url", default="ws://127.0.0.1:8785")
    parser.add_argument("--token-file", default=str(RUNTIME_DIR / "neural_auth_token"))
    parser.add_argument(
        "--artifact",
        help="Content-addressed calibration JSON (generated automatically only for synthetic mode)",
    )
    parser.add_argument("--source", choices=("synthetic", "playback", "brainflow", "lsl"), required=True)
    parser.add_argument("--playback")
    parser.add_argument("--board-id", type=int, default=0)
    parser.add_argument("--serial-port", default="")
    parser.add_argument("--lsl-name", default="HelioxEEG")
    parser.add_argument("--synthetic-frequency", type=float, default=15.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--record-raw", action="store_true", help="Explicitly consent to encrypted local raw EEG")
    parser.add_argument("--recording-file", help="New .neeg destination; never overwritten")
    parser.add_argument("--recording-purpose", default="local accessibility calibration")
    parser.add_argument("--retention-days", type=int, choices=range(1, 366), default=7, metavar="1-365")
    parser.add_argument("--allow-bids-export", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(_run_from_args(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
