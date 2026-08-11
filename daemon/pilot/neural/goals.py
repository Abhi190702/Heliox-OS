"""Compiled neural goal registry; neural strings never become action parameters."""

from __future__ import annotations

from dataclasses import dataclass

from pilot.actions import (
    Action,
    ActionPlan,
    ActionType,
    EmptyParams,
    NotifyParams,
    OpenApplicationParams,
    PermissionTier,
    ProcessParams,
    SystemInfoParams,
    VolumeParams,
    WindowParams,
)


class NeuralGoalError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NeuralGoalDefinition:
    command_id: str
    label: str
    description: str
    action: Action

    def __post_init__(self) -> None:
        if not self.command_id or len(self.command_id) > 64:
            raise NeuralGoalError("neural command_id is invalid")
        if self.action.permission_tier > PermissionTier.USER_WRITE:
            raise NeuralGoalError("neural goals are limited to Tier 0/1 actions")
        if self.action.is_irreversible:
            raise NeuralGoalError("neural goals must be reversible")

    def plan(self) -> ActionPlan:
        action = self.action.model_copy(deep=True)
        return ActionPlan(
            actions=[action],
            explanation=self.description,
            raw_input=f"neural-safe-goal:{self.command_id}",
        )

    def public_summary(self) -> dict[str, object]:
        return {
            "command_id": self.command_id,
            "label": self.label,
            "description": self.description,
            "action_type": self.action.action_type.value,
            "permission_tier": int(self.action.permission_tier),
        }


class NeuralGoalRegistry:
    def __init__(self, goals: tuple[NeuralGoalDefinition, ...] | None = None) -> None:
        configured = goals or default_neural_goals()
        self._goals = {goal.command_id: goal for goal in configured}
        if len(self._goals) != len(configured):
            raise NeuralGoalError("neural command_id values must be unique")

    @property
    def command_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._goals))

    def resolve(self, command_id: str) -> NeuralGoalDefinition:
        goal = self._goals.get(command_id)
        if goal is None:
            raise NeuralGoalError("command_id is not in the compiled neural registry")
        return goal

    def public_summaries(self) -> list[dict[str, object]]:
        return [self._goals[key].public_summary() for key in sorted(self._goals)]


def default_neural_goals() -> tuple[NeuralGoalDefinition, ...]:
    """Small fixed vocabulary suitable for calibrated Tier-0/1 selection."""

    return (
        NeuralGoalDefinition(
            "system-overview",
            "System overview",
            "Read and show current operating-system, CPU, memory, disk, and network information.",
            Action(
                action_type=ActionType.SYSTEM_INFO,
                target="local-system",
                parameters=SystemInfoParams(),
            ),
        ),
        NeuralGoalDefinition(
            "cpu-usage",
            "CPU usage",
            "Read and show current CPU usage.",
            Action(action_type=ActionType.CPU_USAGE, target="local-cpu", parameters=EmptyParams()),
        ),
        NeuralGoalDefinition(
            "memory-usage",
            "Memory usage",
            "Read and show current memory usage.",
            Action(action_type=ActionType.MEMORY_USAGE, target="local-memory", parameters=EmptyParams()),
        ),
        NeuralGoalDefinition(
            "battery-status",
            "Battery status",
            "Read and show current battery status.",
            Action(action_type=ActionType.BATTERY_INFO, target="local-battery", parameters=EmptyParams()),
        ),
        NeuralGoalDefinition(
            "running-processes",
            "Running processes",
            "Read and show the current process list.",
            Action(action_type=ActionType.PROCESS_LIST, target="local-processes", parameters=ProcessParams()),
        ),
        NeuralGoalDefinition(
            "list-windows",
            "Open windows",
            "Read and show the current top-level window list.",
            Action(action_type=ActionType.WINDOW_LIST, target="desktop-windows", parameters=WindowParams()),
        ),
        NeuralGoalDefinition(
            "volume-status",
            "Volume status",
            "Read and show the current system volume.",
            Action(action_type=ActionType.VOLUME_GET, target="system-volume", parameters=VolumeParams()),
        ),
        NeuralGoalDefinition(
            "open-calculator",
            "Open calculator",
            "Open the operating system calculator application.",
            Action(
                action_type=ActionType.OPEN_APPLICATION,
                target="calculator",
                parameters=OpenApplicationParams(name="calculator"),
            ),
        ),
        NeuralGoalDefinition(
            "break-reminder",
            "Break reminder",
            "Show a local reminder to take a short break.",
            Action(
                action_type=ActionType.NOTIFY,
                target="local-notification",
                parameters=NotifyParams(
                    summary="Heliox reminder",
                    body="Take a short break when you reach a safe stopping point.",
                ),
            ),
        ),
    )
