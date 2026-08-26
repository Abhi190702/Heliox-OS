from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pilot.actions import Action, ActionPlan, ActionType, CalendarParams
from pilot.agents.calendar_agent import CalendarAgent


@pytest.fixture
def mock_router():
    return MagicMock()


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.calendar.caldav_url = "http://localhost/caldav"
    config.calendar.caldav_username = "user"
    config.calendar.caldav_password_provider = "cal_pass"
    config.calendar.enabled = True
    config.calendar.ics_files = []
    return config


@pytest.fixture
def mock_vault():
    vault = MagicMock()
    vault.get_key = AsyncMock(return_value="password")
    return vault


@pytest.mark.asyncio
async def test_calendar_agent_parse(mock_router, mock_config, mock_vault, tmp_path):
    agent = CalendarAgent(mock_router, mock_config, mock_vault)

    # Create a dummy .ics file
    ics_file = tmp_path / "test.ics"
    ics_file.write_text("""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Test Event
DTSTART:20231027T100000Z
DTEND:20231027T110000Z
DESCRIPTION:Test Description
END:VEVENT
END:VCALENDAR""")

    plan = ActionPlan(
        actions=[Action(action_type=ActionType.CALENDAR_PARSE, parameters=CalendarParams(file_path=str(ics_file)))]
    )

    results = await agent.handle_task("parse my calendar", plan)
    assert len(results) == 1
    assert results[0].success
    import json

    output = json.loads(results[0].output)
    assert len(output["events"]) == 1
    assert output["events"][0]["summary"] == "Test Event"


@pytest.mark.asyncio
async def test_calendar_parse_uses_all_configured_ics_sources(mock_router, mock_config, mock_vault, tmp_path):
    first = tmp_path / "first.ics"
    first.write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:first\nSUMMARY:First\nDTSTART:20261027T100000Z\nEND:VEVENT\nEND:VCALENDAR"
    )
    second = tmp_path / "second.ics"
    second.write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:second\nSUMMARY:Second\nDTSTART:20261028T100000Z\nEND:VEVENT\nEND:VCALENDAR"
    )
    mock_config.calendar.ics_files = [str(first), str(second)]
    agent = CalendarAgent(mock_router, mock_config, mock_vault)
    plan = ActionPlan(actions=[Action(action_type=ActionType.CALENDAR_PARSE, parameters=CalendarParams())])

    results = await agent.handle_task("parse configured calendars", plan)

    import json

    output = json.loads(results[0].output)
    assert results[0].success is True
    assert {event["uid"] for event in output["events"]} == {"first", "second"}
    assert len(output["sources"]) == 2


@pytest.mark.asyncio
async def test_calendar_list_keeps_local_sources_available_without_caldav(
    mock_router, mock_config, mock_vault, tmp_path
):
    local = tmp_path / "offline.ics"
    local.write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:offline\nSUMMARY:Offline Event\nDTSTART:20261029T100000Z\nEND:VEVENT\nEND:VCALENDAR"
    )
    mock_config.calendar.enabled = False
    mock_config.calendar.ics_files = [str(local)]
    agent = CalendarAgent(mock_router, mock_config, mock_vault)
    plan = ActionPlan(actions=[Action(action_type=ActionType.CALENDAR_LIST_EVENTS, parameters=CalendarParams())])

    results = await agent.handle_task("list events", plan)

    import json

    output = json.loads(results[0].output)
    assert results[0].success is True
    assert output["events"][0]["uid"] == "offline"
    assert output["events"][0]["source"].endswith("offline.ics")
    mock_vault.get_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_list_preserves_local_results_when_caldav_fails(mock_router, mock_config, mock_vault, tmp_path):
    local = tmp_path / "local.ics"
    local.write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:local\nSUMMARY:Local Event\nDTSTART:20261030T100000Z\nEND:VEVENT\nEND:VCALENDAR"
    )
    mock_config.calendar.ics_files = [str(local)]
    mock_vault.get_key.return_value = ""
    agent = CalendarAgent(mock_router, mock_config, mock_vault)
    plan = ActionPlan(actions=[Action(action_type=ActionType.CALENDAR_LIST_EVENTS, parameters=CalendarParams())])

    results = await agent.handle_task("list events", plan)

    import json

    output = json.loads(results[0].output)
    assert results[0].success is True
    assert output["events"][0]["uid"] == "local"
    assert output["warnings"] == [
        "CalDAV: CalDAV configuration is incomplete (URL, username, and saved password are required)"
    ]


@pytest.mark.asyncio
async def test_calendar_agent_sync_mocked(mock_router, mock_config, mock_vault):
    agent = CalendarAgent(mock_router, mock_config, mock_vault)

    plan = ActionPlan(actions=[Action(action_type=ActionType.CALENDAR_SYNC, parameters=CalendarParams())])

    with patch("caldav.DAVClient") as mock_dav:
        mock_client = MagicMock()
        mock_dav.return_value = mock_client
        mock_principal = MagicMock()
        mock_client.principal.return_value = mock_principal
        mock_calendar = MagicMock()
        mock_calendar.name = "Test Calendar"
        mock_principal.calendars.return_value = [mock_calendar]

        results = await agent.handle_task("sync calendar", plan)
        assert len(results) == 1
        assert results[0].success
        import json

        output = json.loads(results[0].output)
        assert output["calendars"] == ["Test Calendar"]
        mock_vault.get_key.assert_awaited_once_with("cal_pass")


@pytest.mark.asyncio
async def test_calendar_agent_requires_explicit_enable(mock_router, mock_config, mock_vault):
    mock_config.calendar.enabled = False
    agent = CalendarAgent(mock_router, mock_config, mock_vault)
    plan = ActionPlan(actions=[Action(action_type=ActionType.CALENDAR_SYNC, parameters=CalendarParams())])

    results = await agent.handle_task("sync calendar", plan)

    assert results[0].success is False
    assert results[0].error == "CalDAV integration is disabled in Settings"
    mock_vault.get_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_agent_deletes_event_by_uid(mock_router, mock_config, mock_vault):
    agent = CalendarAgent(mock_router, mock_config, mock_vault)
    plan = ActionPlan(
        actions=[
            Action(
                action_type=ActionType.CALENDAR_DELETE_EVENT,
                parameters=CalendarParams(calendar_id="Work", event_uid="event-123"),
            )
        ]
    )

    with patch("caldav.DAVClient") as mock_dav:
        calendar = MagicMock(name="calendar")
        calendar.name = "Work"
        event = MagicMock(name="event")
        calendar.event_by_uid.return_value = event
        mock_dav.return_value.principal.return_value.calendars.return_value = [calendar]

        results = await agent.handle_task("delete the event", plan)

    assert results[0].success is True
    calendar.event_by_uid.assert_called_once_with("event-123")
    event.delete.assert_called_once_with()


@pytest.mark.asyncio
async def test_calendar_agent_delete_requires_uid(mock_router, mock_config, mock_vault):
    agent = CalendarAgent(mock_router, mock_config, mock_vault)
    plan = ActionPlan(actions=[Action(action_type=ActionType.CALENDAR_DELETE_EVENT, parameters=CalendarParams())])

    results = await agent.handle_task("delete an event", plan)

    assert results[0].success is False
    assert results[0].error == "Missing event_uid"
    mock_vault.get_key.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_agent_rejects_remote_plain_http(mock_router, mock_config, mock_vault):
    mock_config.calendar.caldav_url = "http://calendar.example.test/dav"
    agent = CalendarAgent(mock_router, mock_config, mock_vault)

    result = await agent.test_connection()

    assert result["status"] == "error"
    assert "must use HTTPS" in result["message"]


@pytest.mark.asyncio
async def test_calendar_connection_status_is_read_only(mock_router, mock_config, mock_vault):
    agent = CalendarAgent(mock_router, mock_config, mock_vault)

    with patch("caldav.DAVClient") as mock_dav:
        calendar = MagicMock()
        calendar.name = "Personal"
        mock_dav.return_value.principal.return_value.calendars.return_value = [calendar]
        result = await agent.test_connection()

    assert result == {"status": "ok", "calendars": ["Personal"]}
    assert calendar.method_calls == []
