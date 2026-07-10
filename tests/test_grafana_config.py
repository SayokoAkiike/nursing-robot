"""Static sanity checks for PR16's Grafana provisioning.

Same approach as tests/test_docker_config.py: no Grafana/Docker daemon
required. These just parse the compose file, the provisioning YAML, and
the dashboard JSON files, and assert the pieces that matter are present
and pointed at each other correctly. Actually loading the dashboards in a
running Grafana is a manual `docker-compose up` + browser check, not
something pytest can verify here.
"""
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARDS_DIR = REPO_ROOT / "grafana" / "provisioning" / "dashboards"
DATASOURCES_DIR = REPO_ROOT / "grafana" / "provisioning" / "datasources"


def _load_compose() -> dict:
    with open(REPO_ROOT / "docker-compose.yml") as f:
        return yaml.safe_load(f)


def _dashboard_json_files() -> list[Path]:
    return sorted(DASHBOARDS_DIR.glob("*.json"))


def test_compose_has_grafana_service():
    compose = _load_compose()
    assert "grafana" in compose["services"]


def test_grafana_service_exposes_port_3000_and_mounts_provisioning():
    grafana = _load_compose()["services"]["grafana"]
    assert "3000:3000" in grafana["ports"]
    assert any(
        v.startswith("./grafana/provisioning:") for v in grafana["volumes"]
    ), "grafana service must mount ./grafana/provisioning so datasources/dashboards load automatically"


def test_grafana_depends_on_db_being_healthy():
    grafana = _load_compose()["services"]["grafana"]
    assert grafana["depends_on"]["db"]["condition"] == "service_healthy"


def test_datasource_provisioning_is_valid_yaml_and_points_at_compose_db():
    with open(DATASOURCES_DIR / "datasource.yml") as f:
        config = yaml.safe_load(f)
    datasource = config["datasources"][0]
    assert datasource["type"] == "postgres"
    assert datasource["url"] == "db:5432"
    assert datasource["database"] == "precare"
    assert datasource["uid"] == "precare-postgres"


def test_dashboards_provider_is_valid_yaml_and_points_at_dashboards_dir():
    with open(DASHBOARDS_DIR / "dashboards.yml") as f:
        config = yaml.safe_load(f)
    provider = config["providers"][0]
    assert provider["type"] == "file"
    assert provider["options"]["path"] == "/etc/grafana/provisioning/dashboards"


def test_at_least_three_dashboard_json_files_exist():
    assert len(_dashboard_json_files()) >= 3


def test_every_dashboard_json_is_valid_and_has_panels():
    for path in _dashboard_json_files():
        with open(path) as f:
            dashboard = json.load(f)
        assert dashboard.get("panels"), f"{path.name} has no panels"
        for panel in dashboard["panels"]:
            assert panel["datasource"]["uid"] == "precare-postgres", (
                f"{path.name} panel {panel.get('title')!r} does not reference the "
                "provisioned postgres datasource"
            )


def test_dashboards_cover_completions_verification_and_state_durations():
    """Regression guard: each of the three analytics areas the roadmap
    called for (completion/cancellation trend, verification failure rate,
    state durations) must actually be represented by a query against the
    corresponding table -- not just present-by-filename."""
    all_sql = ""
    for path in _dashboard_json_files():
        with open(path) as f:
            dashboard = json.load(f)
        for panel in dashboard["panels"]:
            for target in panel["targets"]:
                all_sql += target["rawSql"] + "\n"

    assert "care_requests" in all_sql
    assert "kit_verifications" in all_sql
    assert "task_state_transitions" in all_sql


def test_dashboards_cover_rounding_sessions_and_nurse_escalations():
    """PR27 regression guard, same shape as the check above: the rounding
    workflow's own tables must actually be queried by a dashboard."""
    all_sql = ""
    for path in _dashboard_json_files():
        with open(path) as f:
            dashboard = json.load(f)
        for panel in dashboard["panels"]:
            for target in panel["targets"]:
                all_sql += target["rawSql"] + "\n"

    assert "rounding_sessions" in all_sql
    assert "patient_interactions" in all_sql
    assert "nurse_escalations" in all_sql


def test_at_least_five_dashboard_json_files_exist():
    """PR27 adds two more dashboards (rounding-overview, escalation-queue)
    on top of PR16's three."""
    assert len(_dashboard_json_files()) >= 5
