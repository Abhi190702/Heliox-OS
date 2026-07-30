from __future__ import annotations

from pilot.actions import (
    Action,
    ActionType,
    BrowserParams,
    EmptyParams,
    FileParams,
    ProcessParams,
    ServiceParams,
    ShellCommandParams,
)
from pilot.intelligence.world_model import (
    EffectDomain,
    StructuredTransitionPredictor,
    WorldState,
)


def _state() -> WorldState:
    return WorldState(
        observed_at="2026-07-30T00:00:00+00:00",
        system={"process_count": 100, "disk_usage_fraction": 0.5},
        ui={"active_window": "Heliox"},
        browser={"url": "https://example.com", "dom_state": "observed"},
    )


def test_browser_navigation_predicts_url_and_invalidates_dom() -> None:
    action = Action(
        action_type=ActionType.BROWSER_NAVIGATE,
        target="https://example.org",
        parameters=BrowserParams(url="https://example.org"),
    )

    prediction = StructuredTransitionPredictor().predict(_state(), action)

    assert prediction.predicted_state.browser == {
        "url": "https://example.org",
        "dom_state": "requires_observation",
    }
    assert [effect.domain for effect in prediction.expected_effects[:2]] == [
        EffectDomain.BROWSER,
        EffectDomain.UI,
    ]
    assert prediction.uncertainty == 0.2


def test_browser_click_predicts_possible_dom_change_not_fake_success() -> None:
    action = Action(
        action_type=ActionType.BROWSER_CLICK_TEXT,
        target="Learn more",
        parameters=BrowserParams(text="Learn more"),
    )

    prediction = StructuredTransitionPredictor().predict(_state(), action)

    effect = prediction.expected_effects[0]
    assert effect.operation == "mutate_document"
    assert effect.after == "possibly_changed"
    assert effect.requires_observation is True
    assert prediction.uncertainty == 0.45


def test_file_delete_predicts_absence_and_irreversible_evidence() -> None:
    action = Action(
        action_type=ActionType.FILE_DELETE,
        target="C:/tmp/report.txt",
        parameters=FileParams(path="C:/tmp/report.txt"),
        reversible=False,
        dangerous_flags=["delete"],
    )

    prediction = StructuredTransitionPredictor().predict(_state(), action)

    file_effect = next(effect for effect in prediction.expected_effects if effect.domain == EffectDomain.FILESYSTEM)
    assert file_effect.after == "absent"
    assert file_effect.reversible is False
    assert {item.source for item in prediction.risk_evidence} == {
        "reversibility",
        "validator",
    }


def test_process_and_service_effects_are_both_exposed() -> None:
    action = Action(
        action_type=ActionType.SERVICE_START,
        target="spooler",
        parameters=ServiceParams(name="spooler"),
    )

    prediction = StructuredTransitionPredictor().predict(_state(), action)

    assert prediction.predicted_state.system["process_count"] == 101
    assert {effect.domain for effect in prediction.expected_effects} >= {
        EffectDomain.PROCESS,
        EffectDomain.SERVICE,
        EffectDomain.APPROVAL,
    }


def test_unmodeled_read_action_is_honest_about_observation() -> None:
    action = Action(
        action_type=ActionType.PROCESS_INFO,
        target="42",
        parameters=ProcessParams(pid=42),
    )

    prediction = StructuredTransitionPredictor().predict(_state(), action)

    assert prediction.expected_effects[0].domain == EffectDomain.UNKNOWN
    assert prediction.expected_effects[0].after == "requires_observation"


def test_sensitive_shell_command_is_not_copied_into_prediction() -> None:
    action = Action(
        action_type=ActionType.SHELL_COMMAND,
        target="",
        parameters=ShellCommandParams(command="echo TOP_SECRET"),
    )

    payload = StructuredTransitionPredictor().predict(_state(), action).to_dict()

    assert "TOP_SECRET" not in str(payload)
    assert payload["expected_effects"][0]["target"] == "shell_command"


def test_contract_serializes_enum_domains_and_approval_state() -> None:
    action = Action(
        action_type=ActionType.POWER_SHUTDOWN,
        target="system",
        parameters=EmptyParams(),
    )

    payload = StructuredTransitionPredictor().predict(_state(), action).to_dict()

    assert payload["action_type"] == "power_shutdown"
    assert payload["sources"] == ["structured_rules"]
    assert payload["expected_effects"][-1]["domain"] == "approval"
    assert payload["predicted_state"]["system"]["approval_state"] == "required"
