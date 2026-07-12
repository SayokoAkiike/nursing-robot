"""Tests for roadmap item 6 (realtime UI upgrade).

Both Streamlit apps used to only refresh via a blocking `time.sleep(N);
st.rerun()` pattern -- the patient tablet always looped this way while
waiting/escalated, and the nurse dashboard only did it behind an opt-in
"Auto-refresh" checkbox. Both now use `st.experimental_fragment(run_every=
...)` (the pre-1.37 name for the feature stabilized as `st.fragment` --
this repo pins streamlit==1.35.0) so each section refreshes on its own
timer without a manual checkbox or a script-blocking sleep call.

Two kinds of checks:

  - Source-shape checks: `time.sleep` (the old blocking pattern) is gone
    and `st.experimental_fragment` is actually used, so a future edit
    can't silently regress back to blocking polling.
  - Functional checks via `streamlit.testing.v1.AppTest`: actually run
    each script headlessly (mocking `ui.common.api_client.requests.get`
    the same way tests/test_ui_common_api_client.py already does, so no
    live backend is needed) and confirm it renders without raising, for
    each of the states the fragment functions branch on. This goes a
    step further than tests/test_api.py's existing test_patient_ui_
    importable / test_nurse_dashboard_importable, which only check that
    the file parses as a valid module -- AppTest actually executes the
    fragment bodies.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

ROOT_DIR = Path(__file__).resolve().parent.parent
PATIENT_APP = str(ROOT_DIR / "ui" / "patient_request_app" / "app.py")
NURSE_APP = str(ROOT_DIR / "ui" / "nurse_dashboard" / "app.py")


def _mock_response(json_body):
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


def _source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_patient_app_uses_fragment_not_blocking_sleep():
    source = _source(PATIENT_APP)
    assert "st.experimental_fragment" in source
    # Without `import time`, an actual `time.sleep(...)` call is impossible
    # -- checked this way (rather than searching for the literal substring
    # "time.sleep") because this module's own explanatory comments mention
    # the old pattern by name.
    assert "import time" not in source


def test_nurse_dashboard_uses_fragments_not_blocking_sleep():
    source = _source(NURSE_APP)
    assert "st.experimental_fragment" in source
    assert "import time" not in source
    # The old opt-in checkbox is gone -- refresh is now always-on via the
    # fragments' run_every, not something the nurse has to remember to turn on.
    assert 'st.checkbox("Auto-refresh' not in source


@patch("ui.common.api_client.requests.get")
def test_patient_app_renders_select_screen_with_no_active_task(mock_get):
    mock_get.side_effect = lambda url, *a, **kw: _mock_response([])
    at = AppTest.from_file(PATIENT_APP)
    at.run(timeout=20)
    assert not at.exception
    assert any("Select your request" in m.value for m in at.markdown)
    assert {b.label for b in at.button} >= {"Toileting preparation", "Water request"}


@patch("ui.common.api_client.requests.get")
def test_patient_app_renders_waiting_screen_with_active_task(mock_get):
    task = {
        "request_id": "req-1",
        "patient_id": "PATIENT_A_ROOM_203",
        "request": "Toileting preparation",
        "robot_state": "MOVING_TO_BEDSIDE",
        "kit": "KIT_TOILETING_A",
        "risk": "なし",
        "timestamp": "2026-07-10T00:00:00",
        "robot_id": "ROBOT_1",
    }
    mock_get.side_effect = lambda url, *a, **kw: (
        _mock_response([task]) if url.endswith("/requests") else _mock_response([])
    )
    at = AppTest.from_file(PATIENT_APP)
    at.run(timeout=20)
    assert not at.exception
    assert any("Toileting preparation" in m.value for m in at.markdown)
    assert any("MOVING_TO_BEDSIDE" in c.value for c in at.caption)


@patch("ui.common.api_client.requests.get")
def test_patient_app_renders_escalation_notice(mock_get):
    escalation = {"id": "esc-1", "patient_id": "PATIENT_A_ROOM_203", "status": "PENDING"}
    mock_get.side_effect = lambda url, *a, **kw: (
        _mock_response([escalation]) if url.endswith("/escalations") else _mock_response([])
    )
    at = AppTest.from_file(PATIENT_APP)
    at.run(timeout=20)
    assert not at.exception
    # LABELS["escalation_notified"] -- checked loosely via the wait message
    # both branches share, since the escalation branch takes priority over
    # my_task regardless of whether a delivery task also happens to exist.
    from ui.common.style import LABELS

    assert any(LABELS["escalation_notified"] in m.value for m in at.markdown)


@patch("ui.common.api_client.requests.get")
def test_nurse_dashboard_renders_empty_state_without_error(mock_get):
    mock_get.side_effect = lambda url, *a, **kw: _mock_response([])
    at = AppTest.from_file(NURSE_APP)
    at.run(timeout=20)
    assert not at.exception
    assert any("Waiting for patient request" in m.value for m in at.markdown)


@patch("ui.common.api_client.requests.get")
def test_nurse_dashboard_renders_task_row(mock_get):
    task = {
        "request_id": "req-1",
        "patient_id": "PATIENT_A_ROOM_203",
        "request": "Toileting preparation",
        "robot_state": "WAITING_FOR_NURSE_CONFIRMATION",
        "kit": "KIT_TOILETING_A",
        "risk": "なし",
        "timestamp": "2026-07-10T00:00:00",
        "robot_id": "ROBOT_1",
    }
    mock_get.side_effect = lambda url, *a, **kw: (
        _mock_response([task]) if url.endswith("/requests") else _mock_response([])
    )
    at = AppTest.from_file(NURSE_APP)
    at.run(timeout=20)
    assert not at.exception
    assert any("PATIENT_A_ROOM_203" in m.value for m in at.markdown)
    assert any(b.label == "Release kit" for b in at.button)


@patch("ui.common.api_client.requests.get")
def test_nurse_dashboard_log_table_survives_an_all_none_column(mock_get):
    """Regression test for a real crash found in CI (not reproducible in
    every environment -- dependent on exactly which pyarrow version a
    fresh `pip install` resolves): rounding-workflow log rows leave
    delivery-only fields (request/kit/previous_state/next_state/result)
    entirely None, and delivery-workflow rows leave rounding-only fields
    None the other way -- a column that ends up *entirely* None across
    every row becomes an Arrow null-typed column when converted for
    st.dataframe(), which segfaulted pyarrow outright (not a catchable
    Python exception) in GitHub Actions' resolved pyarrow version. This
    log batch is built so multiple columns (result, message) are all-None
    across every row, on purpose -- the fix (render_log()'s .fillna(""))
    means this must render without exception regardless of which
    pyarrow version is actually installed wherever this test runs."""
    rounding_only_logs = [
        {
            "timestamp": "2026-07-10T00:00:00",
            "event_type": "PATIENT_DETECTED",
            "patient_id": "PATIENT_A_ROOM_203",
            "request": None,
            "kit": None,
            "previous_state": "ROUNDING",
            "next_state": "PATIENT_DETECTED",
            "result": None,
            "message": None,
        },
        {
            "timestamp": "2026-07-10T00:01:00",
            "event_type": "NEED_CLASSIFIED",
            "patient_id": "PATIENT_A_ROOM_203",
            "request": None,
            "kit": None,
            "previous_state": "INTERACTION_STARTED",
            "next_state": "NEED_CLASSIFIED",
            "result": None,
            "message": None,
        },
    ]
    mock_get.side_effect = lambda url, *a, **kw: (
        _mock_response(rounding_only_logs) if url.endswith("/logs") else _mock_response([])
    )
    at = AppTest.from_file(NURSE_APP)
    at.run(timeout=20)
    assert not at.exception
