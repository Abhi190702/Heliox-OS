"""Tamper-evident provenance ledger for neural intent decisions.

The ledger deliberately stores only bounded metadata. Raw EEG samples and feature
vectors remain in the consented encrypted recording path owned by ``neurod``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from pilot.security.permission_audit import ChainVerificationResult


class NeuralAuditStore:
    """Append-only HMAC-chained neural intent provenance."""

    def __init__(self, db_file: Path, key_file: Path, *, key: bytes | None = None) -> None:
        self._db_file = db_file
        self._key_file = key_file
        self._key = key

    async def initialize(self) -> None:
        self._db_file.parent.mkdir(parents=True, exist_ok=True)
        self._key = self._key or self._load_or_create_key()
        async with aiosqlite.connect(self._db_file) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS neural_intent_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL,
                    preview_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    window_start_ns INTEGER NOT NULL,
                    window_end_ns INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    previous_hmac TEXT NOT NULL,
                    entry_hmac TEXT NOT NULL
                )
                """
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_neural_audit_intent ON neural_intent_audit(intent_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_neural_audit_preview ON neural_intent_audit(preview_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_neural_audit_plan ON neural_intent_audit(plan_id)")
            await db.commit()

    async def record_event(
        self,
        *,
        stage: str,
        session_id: str,
        intent_id: str = "",
        preview_id: str = "",
        plan_id: str = "",
        window_start_ns: int = 0,
        window_end_ns: int = 0,
        outcome: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        await self.initialize()
        timestamp = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self._db_file) as db:
            await db.execute("BEGIN IMMEDIATE")
            previous_hmac = await self._last_hmac(db)
            payload = {
                "timestamp": timestamp,
                "stage": self._bounded(stage, 64),
                "session_id": self._bounded(session_id, 64),
                "intent_id": self._bounded(intent_id, 64),
                "preview_id": self._bounded(preview_id, 64),
                "plan_id": self._bounded(plan_id, 128),
                "window_start_ns": max(0, int(window_start_ns)),
                "window_end_ns": max(0, int(window_end_ns)),
                "outcome": self._bounded(outcome, 64),
                "metadata": metadata or {},
                "previous_hmac": previous_hmac,
            }
            entry_hmac = self._sign_payload(payload)
            await db.execute(
                """
                INSERT INTO neural_intent_audit (
                    timestamp, stage, session_id, intent_id, preview_id, plan_id,
                    window_start_ns, window_end_ns, outcome, metadata_json,
                    previous_hmac, entry_hmac
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    payload["stage"],
                    payload["session_id"],
                    payload["intent_id"],
                    payload["preview_id"],
                    payload["plan_id"],
                    payload["window_start_ns"],
                    payload["window_end_ns"],
                    payload["outcome"],
                    self._json_dumps(payload["metadata"]),
                    previous_hmac,
                    entry_hmac,
                ),
            )
            await db.commit()
        return entry_hmac

    async def list_events(self, *, limit: int = 100, intent_id: str | None = None) -> list[dict[str, Any]]:
        await self.initialize()
        query = """
            SELECT id, timestamp, stage, session_id, intent_id, preview_id,
                   plan_id, window_start_ns, window_end_ns, outcome, metadata_json
            FROM neural_intent_audit
        """
        args: tuple[Any, ...] = ()
        if intent_id:
            query += " WHERE intent_id = ?"
            args = (intent_id,)
        query += " ORDER BY id DESC LIMIT ?"
        args = (*args, max(1, min(1000, int(limit))))
        async with aiosqlite.connect(self._db_file) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, args) as cursor:
                rows = await cursor.fetchall()
        events = []
        for row in rows:
            event = dict(row)
            event["metadata"] = json.loads(event.pop("metadata_json"))
            events.append(event)
        return events

    async def verify_chain(self) -> ChainVerificationResult:
        await self.initialize()
        expected_previous = ""
        checked = 0
        async with (
            aiosqlite.connect(self._db_file) as db,
            db.execute(
                """
                SELECT id, timestamp, stage, session_id, intent_id, preview_id,
                       plan_id, window_start_ns, window_end_ns, outcome,
                       metadata_json, previous_hmac, entry_hmac
                FROM neural_intent_audit ORDER BY id ASC
                """
            ) as cursor,
        ):
            async for row in cursor:
                checked += 1
                (
                    row_id,
                    timestamp,
                    stage,
                    session_id,
                    intent_id,
                    preview_id,
                    plan_id,
                    window_start_ns,
                    window_end_ns,
                    outcome,
                    metadata_json,
                    previous_hmac,
                    entry_hmac,
                ) = row
                if previous_hmac != expected_previous:
                    return ChainVerificationResult(False, checked, f"Row {row_id} previous_hmac mismatch")
                payload = {
                    "timestamp": timestamp,
                    "stage": stage,
                    "session_id": session_id,
                    "intent_id": intent_id,
                    "preview_id": preview_id,
                    "plan_id": plan_id,
                    "window_start_ns": window_start_ns,
                    "window_end_ns": window_end_ns,
                    "outcome": outcome,
                    "metadata": json.loads(metadata_json),
                    "previous_hmac": previous_hmac,
                }
                if not hmac.compare_digest(entry_hmac, self._sign_payload(payload)):
                    return ChainVerificationResult(False, checked, f"Row {row_id} entry_hmac mismatch")
                expected_previous = entry_hmac
        return ChainVerificationResult(True, checked)

    async def _last_hmac(self, db: aiosqlite.Connection) -> str:
        async with db.execute("SELECT entry_hmac FROM neural_intent_audit ORDER BY id DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
        return str(row[0]) if row else ""

    def _load_or_create_key(self) -> bytes:
        self._key_file.parent.mkdir(parents=True, exist_ok=True)
        if self._key_file.exists():
            return base64.b64decode(self._key_file.read_text(encoding="utf-8"))
        key = secrets.token_bytes(32)
        self._key_file.write_text(base64.b64encode(key).decode("ascii"), encoding="utf-8")
        try:
            os.chmod(self._key_file, 0o600)
        except OSError:
            pass
        return key

    def _sign_payload(self, payload: dict[str, Any]) -> str:
        if self._key is None:
            self._key = self._load_or_create_key()
        return hmac.new(self._key, self._json_dumps(payload).encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _bounded(value: str, limit: int) -> str:
        value = str(value)
        if len(value) > limit or any(unicodedata.category(character).startswith("C") for character in value):
            raise ValueError("neural audit field is invalid")
        return value

    @staticmethod
    def _json_dumps(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
