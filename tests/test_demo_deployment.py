"""Tests for the public demo deployment (streamlit_app.py + pages/).

These actually bind a real port (backend_bootstrap.DEMO_BACKEND_PORT) via
a real uvicorn thread. Genuinely exercises the same code path a Streamlit
Community Cloud visitor's browser would hit, not a mock of it -- but
because that's a real, persistent server, this file's fixture explicitly
shuts it down again once every test here has run (see
backend_bootstrap.stop_backend_for_tests()), rather than leaving it (and
the DATABASE_URL/get_settings() state it captured at startup) alive for
the rest of a 400+ test pytest session. The real Streamlit Cloud
deployment never calls that cleanup path -- there, the process's entire
lifetime *is* the deployment's lifetime, so a server that runs forever is
exactly the intended behavior.

Isolation note (a real bug caught during review, not a hypothetical): an
earlier version of this fixture only reset backend.db.session's engine
and cleared backend.core.config.get_settings()'s @lru_cache, without
actually stopping the server thread itself. That was enough to fix the
failure this docstring originally described in isolation, but a lingering
real server thread turned out to still cause a different, harder-to-pin-
down failure once the *entire* test suite ran (not reproducible from a
handful of files run together) -- fully stopping the thread, not just
its DB configuration, was the fix that held up under the full suite.
"""
import os

import pytest
import requests
from streamlit.testing.v1 import AppTest

ENTRY_FILES = [
    "demo/streamlit_app.py",
    "demo/pages/1_🛏️_患者用タブレット.py",
    "demo/pages/2_🩺_看護師ダッシュボード.py",
    "demo/pages/3_🚶_巡回・要望分類デモ.py",
    "demo/pages/4_📊_Analytics.py",
]


@pytest.fixture(scope="module", autouse=True)
def isolated_demo_database(tmp_path_factory):
    demo_db_path = tmp_path_factory.mktemp("demo_deploy") / "precare_demo_test.db"
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{demo_db_path}"

    # backend.core.config.get_settings() is @lru_cache'd. If any earlier
    # test in the suite already called it (directly or via the FastAPI
    # app import chain) before DATABASE_URL was set above, that cached
    # Settings object has database_url=None frozen into it -- setting the
    # env var here would then be silently ignored by every later
    # get_settings() call, and _default_url()'s "settings.database_url or
    # <hardcoded fallback>" would fall through to the hardcoded
    # "sqlite:///./data/precare.db" (the real dev DB file) instead of this
    # fixture's isolated temp path. Clearing the cache *before* starting
    # the backend, not just after, is what actually closes this gap --
    # clearing only in teardown (an earlier version of this fixture) left
    # the setup-time staleness intact.
    #
    # Clearing the settings cache alone still wasn't enough, though:
    # backend.db.session.get_engine()'s own lazy-init guard is `if _engine
    # is None: configure_engine()` -- once ANY earlier test's `robot_
    # storage` fixture teardown has already configured a (correct,
    # default-pointing) engine, `_engine` is no longer None, so that guard
    # never re-fires and this fixture's DATABASE_URL change gets ignored
    # by the *engine* layer even though get_settings() itself is correct.
    # configure_engine() must be called explicitly here too.
    from backend.core.config import get_settings
    from backend.db import session as db_session

    get_settings.cache_clear()
    db_session.configure_engine()
    try:
        yield
    finally:
        from ui.common.backend_bootstrap import stop_backend_for_tests

        stop_backend_for_tests()

        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original

        get_settings.cache_clear()
        db_session.configure_engine()


def test_backend_bootstrap_starts_a_real_reachable_backend():
    from ui.common.backend_bootstrap import DEMO_BACKEND_URL, start_backend

    assert start_backend() is True
    r = requests.get(f"{DEMO_BACKEND_URL}/state", timeout=3)
    assert r.status_code == 200


def test_all_entry_files_render_without_exception():
    for path in ENTRY_FILES:
        at = AppTest.from_file(path, default_timeout=20)
        at.run()
        assert not at.exception, f"{path} raised: {at.exception}"


def test_classification_demo_page_creates_a_real_escalation_a_nurse_can_see():
    """End-to-end: the rounding-demo page's 'run' button really calls the
    real API sequence (start -> detect-patient -> start-interaction ->
    classify-need -> escalate), and the resulting escalation really shows
    up on the nurse dashboard page -- i.e. the two pages genuinely share
    one backend/DB, which is the entire point of running them as one
    Streamlit Cloud deployment instead of two."""
    demo = AppTest.from_file("demo/pages/3_🚶_巡回・要望分類デモ.py", default_timeout=20)
    demo.run()
    demo.text_input[0].set_value("トイレに行きたいです").run()
    run_button = next(b for b in demo.button if b.label == "巡回を実行して分類する")
    run_button.click().run()
    assert not demo.exception

    demo_texts = " ".join(m.value for m in demo.markdown)
    assert "toileting" in demo_texts
    assert "エスカレーション" in demo_texts

    nurse = AppTest.from_file("demo/pages/2_🩺_看護師ダッシュボード.py", default_timeout=20)
    nurse.run()
    assert not nurse.exception
    nurse_texts = " ".join(m.value for m in nurse.markdown)
    assert "PATIENT_A_ROOM_203" in nurse_texts


def test_analytics_seed_produces_enough_patients_for_anomaly_detection():
    """Calls demo_seed.seed_anomaly_demo_data() directly rather than
    through the Analytics page's button -- AppTest + a real st.rerun()
    immediately after ~25 synchronous HTTP calls proved unreliable in
    this project's sandbox specifically (intermittent segfaults, not
    reproducible via direct function calls, and not something this
    project's own real Streamlit Cloud deployment goes through the same
    testing harness for anyway). What actually matters -- the seeded
    data crosses escalation_anomaly_service.MIN_PATIENTS_FOR_ANALYSIS and
    correctly flags the one deliberate outlier patient -- is fully
    covered by calling the real functions directly, same as this file's
    other tests call real API endpoints directly via `requests`."""
    from ui.common.backend_bootstrap import start_backend
    from ui.common.demo_seed import seed_anomaly_demo_data

    start_backend()
    result = seed_anomaly_demo_data()
    assert len(result["created_patients"]) == 7

    from backend.services.escalation_anomaly_service import analyze

    analysis = analyze()
    # >= rather than == : other tests in this file (e.g. the classification
    # demo page test above) share this same module-scoped backend/DB and
    # may have already created their own patient's escalation data --
    # what this test actually needs to prove is that *this* seed batch
    # crossed the analysis threshold and its outlier got flagged, not an
    # exact count of every patient anyone else in this file happened to
    # create too.
    assert analysis["total_patients_analyzed"] >= 7
    anomalous_ids = {p["patient_id"] for p in analysis["anomalous_patients"]}
    assert result["outlier_patient_id"] in anomalous_ids
