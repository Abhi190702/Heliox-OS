from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import aiohttp
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from pilot.air_handoff import (
    AirHandoffError,
    AirHandoffManager,
    AirHandoffServer,
    _b64u,
    _canonical_request,
    _unb64u,
)
from pilot.config import PilotConfig, _merge_config, _validate_config_types


class FakeVault:
    def __init__(self) -> None:
        self.available = True
        self.values: dict[str, str] = {}

    async def get_key(self, provider: str) -> str | None:
        return self.values.get(provider)

    async def store_key(self, provider: str, value: str) -> None:
        self.values[provider] = value

    async def delete_key(self, provider: str) -> None:
        self.values.pop(provider, None)


async def pair_device(
    manager: AirHandoffManager,
    *,
    name: str = "Test phone",
    base_url: str = "http://127.0.0.1:8787",
) -> tuple[dict[str, str], bytes]:
    pairing = manager.start_pairing(base_url)
    secret = _unb64u(parse_qs(urlparse(pairing["pairing_url"]).fragment)["pair"][0])
    client_private = x25519.X25519PrivateKey.generate()
    client_public = client_private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    response = await manager.complete_pairing(
        device_name=name,
        client_public_key=client_public,
        client_proof=hmac.new(secret, b"pair-v1:" + client_public, hashlib.sha256).digest(),
    )
    server_public = _unb64u(response["server_public_key"])
    expected_server_proof = hmac.new(
        secret,
        b"server-v1:" + server_public + client_public,
        hashlib.sha256,
    ).digest()
    assert hmac.compare_digest(expected_server_proof, _unb64u(response["server_proof"]))
    wrapping_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=secret,
        info=b"heliox-air-handoff-pair-v1",
    ).derive(client_private.exchange(x25519.X25519PublicKey.from_public_bytes(server_public)))
    credential = json.loads(
        AESGCM(wrapping_key)
        .decrypt(
            _unb64u(response["nonce"]),
            _unb64u(response["credential"]),
            b"heliox-air-handoff-credential-v1",
        )
        .decode()
    )
    return credential, _unb64u(credential["device_secret"])


def signed_headers(
    credential: dict[str, str],
    secret: bytes,
    *,
    method: str,
    path: str,
    body: bytes = b"",
    nonce: str = "test-request-nonce",
) -> dict[str, str]:
    timestamp = str(time.time())
    signature = hmac.new(
        secret,
        _canonical_request(method, path, timestamp, nonce, body),
        hashlib.sha256,
    ).digest()
    return {
        "X-Heliox-Device": credential["device_id"],
        "X-Heliox-Time": timestamp,
        "X-Heliox-Nonce": nonce,
        "X-Heliox-Signature": _b64u(signature),
    }


def test_air_handoff_config_is_opt_in_and_bounded() -> None:
    config = PilotConfig()
    assert config.air_handoff.enabled is False
    assert config.air_handoff.port == 8787
    _validate_config_types({"air_handoff": {"enabled": True, "port": 9999, "max_transfer_mb": 50}})
    merged = _merge_config(
        config,
        {"air_handoff": {"enabled": True, "port": 80, "max_transfer_mb": 999}},
    )
    assert merged.air_handoff.enabled is True
    assert merged.air_handoff.port == 1024
    assert merged.air_handoff.max_transfer_mb == 250


@pytest.mark.asyncio
async def test_pair_authenticate_reject_replay_and_revoke(tmp_path: Path) -> None:
    vault = FakeVault()
    manager = AirHandoffManager(vault, data_dir=tmp_path)
    credential, secret = await pair_device(manager)
    path = "/api/pending"
    headers = signed_headers(credential, secret, method="GET", path=path)

    device = await manager.authenticate_request(
        device_id=headers["X-Heliox-Device"],
        method="GET",
        path=path,
        timestamp=headers["X-Heliox-Time"],
        nonce=headers["X-Heliox-Nonce"],
        signature=headers["X-Heliox-Signature"],
        body=b"",
    )
    assert device.name == "Test phone"
    with pytest.raises(AirHandoffError, match="Replay"):
        await manager.authenticate_request(
            device_id=headers["X-Heliox-Device"],
            method="GET",
            path=path,
            timestamp=headers["X-Heliox-Time"],
            nonce=headers["X-Heliox-Nonce"],
            signature=headers["X-Heliox-Signature"],
            body=b"",
        )

    await manager.revoke_device(credential["device_id"])
    assert await manager.list_devices() == []
    assert vault.values == {}


@pytest.mark.asyncio
async def test_drop_is_encrypted_and_visible_only_to_target(tmp_path: Path) -> None:
    vault = FakeVault()
    manager = AirHandoffManager(vault, data_dir=tmp_path)
    first, first_secret = await pair_device(manager, name="First phone")
    second, _ = await pair_device(manager, name="Second phone")

    draft = await manager.grab_text("private handoff", filename="note.txt")
    assert draft["kind"] == "text"
    transfer = await manager.drop(first["device_id"])
    transfer_id = transfer["transfer_id"]
    assert await manager.pending_for(second["device_id"]) == []

    pending = await manager.pending_for(first["device_id"])
    assert [item["transfer_id"] for item in pending] == [transfer_id]
    _, clear = await manager.transfer_bytes(first["device_id"], transfer_id)
    encrypted = await manager.encrypt_bytes_for(first["device_id"], clear, aad=f"transfer-v1:{transfer_id}".encode())
    assert b"private handoff" not in encrypted
    assert (
        AESGCM(first_secret).decrypt(
            encrypted[:12],
            encrypted[12:],
            f"transfer-v1:{transfer_id}".encode(),
        )
        == b"private handoff"
    )
    with pytest.raises(AirHandoffError, match="unavailable"):
        await manager.transfer_bytes(second["device_id"], transfer_id)

    await manager.acknowledge(first["device_id"], transfer_id)
    status = await manager.status()
    assert status["ready_transfers"] == 0


@pytest.mark.asyncio
async def test_file_grab_snapshots_content_before_original_changes(tmp_path: Path) -> None:
    manager = AirHandoffManager(FakeVault(), data_dir=tmp_path / "handoff")
    credential, _ = await pair_device(manager)
    source = tmp_path / "report.txt"
    source.write_text("version one", encoding="utf-8")

    draft = await manager.grab_file(str(source))
    source.write_text("version two", encoding="utf-8")
    transfer = await manager.drop(credential["device_id"])
    metadata, payload = await manager.transfer_bytes(credential["device_id"], transfer["transfer_id"])

    assert draft["filename"] == "report.txt"
    assert metadata.filename == "report.txt"
    assert payload == b"version one"


@pytest.mark.asyncio
async def test_receiver_serves_hardened_assets_and_authenticated_poll(tmp_path: Path) -> None:
    manager = AirHandoffManager(FakeVault(), data_dir=tmp_path)
    server = AirHandoffServer(manager, host="127.0.0.1", port=0)
    await server.start()
    try:
        base_url = f"http://127.0.0.1:{server.port}"
        credential, secret = await pair_device(manager, base_url=base_url)
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url) as response:
                assert response.status == 200
                assert "default-src 'self'" in response.headers["Content-Security-Policy"]
                assert response.headers["Cache-Control"] == "no-store"

            path = "/api/pending"
            headers = signed_headers(
                credential,
                secret,
                method="GET",
                path=path,
                nonce="receiver-poll-nonce",
            )
            async with session.get(base_url + path, headers=headers) as response:
                assert response.status == 200
                envelope = await response.json()
            pending = AESGCM(secret).decrypt(
                _unb64u(envelope["nonce"]),
                _unb64u(envelope["ciphertext"]),
                b"pending-v1",
            )
            assert json.loads(pending) == []

            draft = await manager.grab_text("private metadata", filename="secret-name.txt")
            transfer = await manager.drop(credential["device_id"])
            path = f"/api/transfers/{transfer['transfer_id']}"
            headers = signed_headers(
                credential,
                secret,
                method="GET",
                path=path,
                nonce="receiver-transfer-nonce",
            )
            async with session.get(base_url + path, headers=headers) as response:
                assert response.status == 200
                assert response.headers["Content-Type"] == "application/vnd.heliox.encrypted"
                assert "X-Heliox-Filename" not in response.headers
                assert "X-Heliox-Mime" not in response.headers
                assert "X-Heliox-Transfer" not in response.headers
                encrypted_transfer = await response.read()
            assert draft["filename"] == "secret-name.txt"
            assert b"secret-name.txt" not in encrypted_transfer
    finally:
        await server.stop()
