"""Unified, inspectable world-model prediction contract.

The structured predictor describes likely state transitions before execution.
It is advisory: validators, deterministic policy, approval, and verification
remain the authority for whether an action may run and whether it succeeded.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

from pilot.actions import ActionType

if TYPE_CHECKING:
    from pilot.actions import Action
    from pilot.security.risk_observation import OsSnapshot


class EffectDomain(StrEnum):
    BROWSER = "browser"
    UI = "ui"
    WINDOW = "window"
    PROCESS = "process"
    FILESYSTEM = "filesystem"
    SERVICE = "service"
    PACKAGE = "package"
    SYSTEM = "system"
    APPROVAL = "approval"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ExpectedEffect:
    domain: EffectDomain
    operation: str
    target: str
    before: Any = None
    after: Any = None
    confidence: float = 1.0
    reversible: bool = True
    requires_observation: bool = True
    evidence: str = ""


@dataclass(frozen=True, slots=True)
class RiskEvidence:
    source: str
    score: float
    reason: str
    deterministic: bool = False


@dataclass(frozen=True, slots=True)
class WorldState:
    observed_at: str
    system: dict[str, Any] = field(default_factory=dict)
    ui: dict[str, Any] = field(default_factory=dict)
    browser: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> WorldState:
        return cls(observed_at=datetime.now(UTC).isoformat())

    @classmethod
    def from_os_snapshot(
        cls,
        snapshot: OsSnapshot,
        *,
        ui: dict[str, Any] | None = None,
        browser: dict[str, Any] | None = None,
    ) -> WorldState:
        return cls(
            observed_at=datetime.now(UTC).isoformat(),
            system={
                "process_count": snapshot.proc_count,
                "disk_usage_fraction": snapshot.disk_usage_fraction,
                "memory_usage_fraction": snapshot.memory_usage_fraction,
            },
            ui=dict(ui or {}),
            browser=dict(browser or {}),
        )


@dataclass(frozen=True, slots=True)
class WorldPrediction:
    action_type: str
    predicted_state: WorldState
    expected_effects: tuple[ExpectedEffect, ...]
    uncertainty: float
    risk_evidence: tuple[RiskEvidence, ...]
    sources: tuple[str, ...]
    model_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "predicted_state": asdict(self.predicted_state),
            "expected_effects": [{**asdict(effect), "domain": effect.domain.value} for effect in self.expected_effects],
            "uncertainty": self.uncertainty,
            "risk_evidence": [asdict(item) for item in self.risk_evidence],
            "sources": list(self.sources),
            "model_version": self.model_version,
        }


class WorldPredictor(Protocol):
    def predict(
        self,
        current_state: WorldState,
        candidate_action: Action,
    ) -> WorldPrediction: ...


_BROWSER_NAVIGATION = {
    ActionType.BROWSER_NAVIGATE,
    ActionType.OPEN_URL,
    ActionType.BROWSER_BACK,
    ActionType.BROWSER_FORWARD,
    ActionType.BROWSER_REFRESH,
}
_BROWSER_MUTATION = {
    ActionType.BROWSER_CLICK,
    ActionType.BROWSER_CLICK_TEXT,
    ActionType.BROWSER_TYPE,
    ActionType.BROWSER_SELECT,
    ActionType.BROWSER_FILL_FORM,
    ActionType.BROWSER_EXECUTE_JS,
}
_WINDOW_ACTIONS = {
    ActionType.WINDOW_FOCUS,
    ActionType.WINDOW_CLOSE,
    ActionType.WINDOW_MINIMIZE,
    ActionType.WINDOW_MAXIMIZE,
}
_PROCESS_START = {
    ActionType.OPEN_APPLICATION,
    ActionType.SHELL_COMMAND,
    ActionType.SHELL_SCRIPT,
    ActionType.PTY_EXEC,
    ActionType.CODE_EXECUTE,
    ActionType.SERVICE_START,
}
_PROCESS_STOP = {
    ActionType.PROCESS_KILL,
    ActionType.SERVICE_STOP,
}
_FILE_ACTIONS = {
    ActionType.FILE_WRITE,
    ActionType.FILE_DELETE,
    ActionType.FILE_MOVE,
    ActionType.FILE_COPY,
    ActionType.FILE_PERMISSIONS,
    ActionType.DOWNLOAD_FILE,
}
_SERVICE_ACTIONS = {
    ActionType.SERVICE_START,
    ActionType.SERVICE_STOP,
    ActionType.SERVICE_RESTART,
    ActionType.SERVICE_ENABLE,
    ActionType.SERVICE_DISABLE,
}
_PACKAGE_ACTIONS = {
    ActionType.PACKAGE_INSTALL,
    ActionType.PACKAGE_REMOVE,
    ActionType.PACKAGE_UPDATE,
}


class StructuredTransitionPredictor:
    """Predict first-party OS/UI effects without executing the action."""

    model_version = "structured-transition-v1"

    def predict(
        self,
        current_state: WorldState,
        candidate_action: Action,
    ) -> WorldPrediction:
        action_type = candidate_action.action_type
        params = candidate_action.parameters.model_dump()
        predicted = WorldState(
            observed_at=current_state.observed_at,
            system=deepcopy(current_state.system),
            ui=deepcopy(current_state.ui),
            browser=deepcopy(current_state.browser),
        )
        effects: list[ExpectedEffect] = []
        uncertainty = self._uncertainty(action_type)

        if action_type in _BROWSER_NAVIGATION:
            target = self._safe_target(candidate_action, params)
            before_url = current_state.browser.get("url")
            after_url = target if action_type in {ActionType.BROWSER_NAVIGATE, ActionType.OPEN_URL} else "changed"
            predicted.browser["url"] = after_url
            predicted.browser["dom_state"] = "requires_observation"
            effects.extend(
                (
                    ExpectedEffect(
                        EffectDomain.BROWSER,
                        "navigate",
                        target or action_type.value,
                        before=before_url,
                        after=after_url,
                        confidence=0.9 if target else 0.65,
                        evidence="navigation action contract",
                    ),
                    ExpectedEffect(
                        EffectDomain.UI,
                        "replace_accessibility_tree",
                        "active browser document",
                        before=current_state.browser.get("dom_state"),
                        after="requires_observation",
                        confidence=0.85,
                        evidence="navigation invalidates prior DOM and accessibility state",
                    ),
                )
            )
        elif action_type in _BROWSER_MUTATION:
            target = self._safe_target(candidate_action, params)
            predicted.browser["dom_state"] = "possibly_changed"
            effects.append(
                ExpectedEffect(
                    EffectDomain.BROWSER,
                    "mutate_document",
                    target or action_type.value,
                    after="possibly_changed",
                    confidence=0.65,
                    reversible=action_type != ActionType.BROWSER_EXECUTE_JS,
                    evidence="interactive browser actions can mutate DOM, accessibility, or navigation state",
                )
            )
        elif action_type in _WINDOW_ACTIONS or action_type == ActionType.OPEN_APPLICATION:
            target = self._safe_target(candidate_action, params)
            operation = action_type.value.removeprefix("window_").removeprefix("open_")
            predicted.ui["active_window"] = target if operation in {"focus", "application"} else "changed"
            effects.append(
                ExpectedEffect(
                    EffectDomain.WINDOW,
                    operation,
                    target or "selected window",
                    before=current_state.ui.get("active_window"),
                    after=predicted.ui["active_window"],
                    confidence=0.85,
                    evidence="window-manager action contract",
                )
            )

        process_delta = int(action_type in _PROCESS_START) - int(action_type in _PROCESS_STOP)
        if process_delta:
            before_count = current_state.system.get("process_count")
            after_count = before_count + process_delta if isinstance(before_count, int) else "changed"
            predicted.system["process_count"] = after_count
            effects.append(
                ExpectedEffect(
                    EffectDomain.PROCESS,
                    "start" if process_delta > 0 else "stop",
                    self._safe_target(candidate_action, params) or action_type.value,
                    before=before_count,
                    after=after_count,
                    confidence=0.7,
                    reversible=action_type not in {ActionType.PROCESS_KILL, ActionType.SHELL_SCRIPT},
                    evidence="process lifecycle action contract",
                )
            )

        if action_type in _FILE_ACTIONS:
            path = self._safe_target(candidate_action, params)
            operation = action_type.value.removeprefix("file_").removeprefix("download_")
            effects.append(
                ExpectedEffect(
                    EffectDomain.FILESYSTEM,
                    operation,
                    path or "declared file target",
                    after=self._file_after_state(action_type, params),
                    confidence=0.9,
                    reversible=candidate_action.reversible,
                    evidence="filesystem action contract",
                )
            )

        if action_type in _SERVICE_ACTIONS:
            state = action_type.value.removeprefix("service_")
            effects.append(
                ExpectedEffect(
                    EffectDomain.SERVICE,
                    state,
                    self._safe_target(candidate_action, params) or "declared service",
                    after=state,
                    confidence=0.9,
                    evidence="service-manager action contract",
                )
            )

        if action_type in _PACKAGE_ACTIONS:
            operation = action_type.value.removeprefix("package_")
            effects.append(
                ExpectedEffect(
                    EffectDomain.PACKAGE,
                    operation,
                    self._safe_target(candidate_action, params) or "declared package",
                    after=operation,
                    confidence=0.8,
                    reversible=operation != "remove",
                    evidence="package-manager action contract",
                )
            )

        approval_state = "required" if candidate_action.requires_confirmation else "not_required"
        predicted.system["approval_state"] = approval_state
        effects.append(
            ExpectedEffect(
                EffectDomain.APPROVAL,
                "gate",
                action_type.value,
                after=approval_state,
                confidence=1.0,
                evidence="deterministic permission tier",
            )
        )

        if len(effects) == 1:
            effects.insert(
                0,
                ExpectedEffect(
                    EffectDomain.UNKNOWN,
                    "observe_result",
                    action_type.value,
                    after="requires_observation",
                    confidence=0.35,
                    evidence="no structured transition rule for this action type",
                ),
            )

        return WorldPrediction(
            action_type=action_type.value,
            predicted_state=predicted,
            expected_effects=tuple(effects),
            uncertainty=uncertainty,
            risk_evidence=self._risk_evidence(candidate_action),
            sources=("structured_rules",),
            model_version=self.model_version,
        )

    @staticmethod
    def _safe_target(action: Action, params: dict[str, Any]) -> str:
        if action.action_type in {
            ActionType.SHELL_COMMAND,
            ActionType.SHELL_SCRIPT,
            ActionType.PTY_EXEC,
            ActionType.CODE_EXECUTE,
            ActionType.BROWSER_EXECUTE_JS,
        }:
            return action.action_type.value
        for key in (
            "path",
            "output_path",
            "destination",
            "url",
            "name",
            "title",
            "process_name",
            "value_name",
            "selector",
            "text",
        ):
            value = params.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()[:300]
        return action.target.strip()[:300]

    @staticmethod
    def _file_after_state(action_type: ActionType, params: dict[str, Any]) -> str:
        if action_type == ActionType.FILE_DELETE:
            return "absent"
        if action_type == ActionType.FILE_MOVE:
            return f"moved_to:{str(params.get('destination') or 'declared destination')[:200]}"
        if action_type in {ActionType.FILE_WRITE, ActionType.FILE_COPY, ActionType.DOWNLOAD_FILE}:
            return "present_or_updated"
        return "metadata_changed"

    @staticmethod
    def _uncertainty(action_type: ActionType) -> float:
        if action_type in {
            ActionType.SHELL_COMMAND,
            ActionType.SHELL_SCRIPT,
            ActionType.PTY_EXEC,
            ActionType.CODE_EXECUTE,
            ActionType.BROWSER_EXECUTE_JS,
        }:
            return 0.85
        if action_type in _BROWSER_MUTATION:
            return 0.45
        if action_type in _BROWSER_NAVIGATION:
            return 0.2
        if action_type in _FILE_ACTIONS | _SERVICE_ACTIONS | _PACKAGE_ACTIONS | _WINDOW_ACTIONS:
            return 0.15
        return 0.35

    @staticmethod
    def _risk_evidence(action: Action) -> tuple[RiskEvidence, ...]:
        evidence: list[RiskEvidence] = []
        if action.requires_root:
            evidence.append(RiskEvidence("permission_tier", 1.0, "Action requests root privileges", True))
        if action.is_irreversible:
            evidence.append(RiskEvidence("reversibility", 0.9, "Action may be irreversible", True))
        if action.dangerous_flags:
            evidence.append(
                RiskEvidence(
                    "validator",
                    min(1.0, 0.55 + 0.1 * len(action.dangerous_flags)),
                    f"Validator reported {len(action.dangerous_flags)} dangerous flag(s)",
                    True,
                )
            )
        return tuple(evidence)
