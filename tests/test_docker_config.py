"""Static sanity checks for PR13's Dockerfile / docker-compose.yml.

These don't require a Docker daemon (not available in CI or most sandboxed
dev environments) -- they just parse the files and assert the pieces that
matter are present and pointed at each other correctly. Actually building
and running the containers is a manual `docker-compose up` check, not
something pytest can verify here.
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_compose() -> dict:
    with open(REPO_ROOT / "docker-compose.yml") as f:
        return yaml.safe_load(f)


def test_docker_compose_is_valid_yaml_with_expected_services():
    compose = _load_compose()
    assert "db" in compose["services"]
    assert "backend" in compose["services"]


def test_backend_service_builds_from_repo_root_dockerfile():
    compose = _load_compose()
    backend = compose["services"]["backend"]
    assert backend["build"]["context"] == "."
    assert backend["build"]["dockerfile"] == "Dockerfile"
    assert (REPO_ROOT / "Dockerfile").exists()


def test_backend_depends_on_db_being_healthy():
    compose = _load_compose()
    backend = compose["services"]["backend"]
    assert backend["depends_on"]["db"]["condition"] == "service_healthy"


def test_backend_database_url_points_at_compose_db_service_not_localhost():
    """Inside the compose network, the DB is reachable by service name
    ("db"), not "localhost" -- localhost inside the backend container would
    mean the container itself, which has no Postgres running."""
    compose = _load_compose()
    database_url = compose["services"]["backend"]["environment"]["DATABASE_URL"]
    assert "@db:5432/" in database_url
    assert "localhost" not in database_url


def test_backend_exposes_port_8000():
    compose = _load_compose()
    backend = compose["services"]["backend"]
    assert "8000:8000" in backend["ports"]


def test_dockerfile_exposes_8000_and_runs_uvicorn():
    content = (REPO_ROOT / "Dockerfile").read_text()
    assert "EXPOSE 8000" in content
    assert "uvicorn" in content
    assert "backend.main:app" in content


def test_dockerfile_installs_from_the_same_requirements_txt_as_local_dev():
    """See the Dockerfile's own comment: intentionally the same
    requirements.txt as `pip install -r requirements.txt` in the README's
    Quick Start, not a separate slimmed-down file, so the image never
    silently drifts from what's actually tested."""
    content = (REPO_ROOT / "Dockerfile").read_text()
    assert "requirements.txt" in content
