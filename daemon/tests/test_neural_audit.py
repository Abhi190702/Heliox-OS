from __future__ import annotations

import aiosqlite
import pytest

from pilot.neural.audit import NeuralAuditStore


@pytest.fixture
def store(tmp_path):
    return NeuralAuditStore(tmp_path / "neural.db", tmp_path / "neural.key")


@pytest.mark.asyncio
async def test_neural_audit_links_window_intent_preview_plan_and_result(store) -> None:
    common = {
        "session_id": "session-1",
        "intent_id": "intent-1",
        "window_start_ns": 100,
        "window_end_ns": 200,
    }
    await store.record_event(stage="intent_accepted", outcome="accepted", **common)
    await store.record_event(
        stage="preview_created",
        preview_id="preview-1",
        outcome="previewed",
        **common,
    )
    await store.record_event(
        stage="commit_authorized",
        preview_id="preview-1",
        plan_id="plan-1",
        outcome="authorized",
        **common,
    )
    await store.record_event(
        stage="result",
        preview_id="preview-1",
        plan_id="plan-1",
        outcome="completed",
        **common,
    )

    events = list(reversed(await store.list_events(intent_id="intent-1")))
    assert [event["stage"] for event in events] == [
        "intent_accepted",
        "preview_created",
        "commit_authorized",
        "result",
    ]
    assert events[-1]["plan_id"] == "plan-1"
    assert (await store.verify_chain()).valid is True


@pytest.mark.asyncio
async def test_neural_audit_detects_tampering(store) -> None:
    await store.record_event(
        stage="intent_accepted",
        session_id="session-1",
        intent_id="intent-1",
        outcome="accepted",
    )
    async with aiosqlite.connect(store._db_file) as db:
        await db.execute("UPDATE neural_intent_audit SET outcome = 'forged' WHERE id = 1")
        await db.commit()
    verification = await store.verify_chain()
    assert verification.valid is False
    assert "entry_hmac mismatch" in verification.error


@pytest.mark.asyncio
async def test_neural_audit_rejects_unbounded_or_control_fields(store) -> None:
    with pytest.raises(ValueError, match="audit field"):
        await store.record_event(
            stage="intent\naccepted",
            session_id="session-1",
            outcome="accepted",
        )
