from pilot.actions import ActionType
from pilot.agents.planner import Planner


def test_system_information_uses_fast_path_for_spoken_transcription_variant():
    plan = Planner._try_fast_path("true system information")

    assert plan is not None
    assert [action.action_type for action in plan.actions] == [ActionType.SYSTEM_INFO]


def test_system_information_fast_path_is_bounded_to_short_status_queries():
    assert (
        Planner._try_fast_path("research system information formats and write a detailed comparison of every standard")
        is None
    )
