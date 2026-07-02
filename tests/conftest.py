import os
import pytest

os.environ.setdefault("NURSE_TOKEN", "precare-dev-token-2026")

import backend.storage as storage

NURSE_TOKEN = "precare-dev-token-2026"
HEADERS = {"x-nurse-token": NURSE_TOKEN}


@pytest.fixture
def robot_storage(tmp_path):
    """各テストで独立したJSONファイルを使う。"""
    orig_state = storage.STATE_FILE
    orig_log   = storage.LOG_FILE
    storage.STATE_FILE = tmp_path / "state.json"
    storage.LOG_FILE   = tmp_path / "log.json"
    yield storage
    storage.STATE_FILE = orig_state
    storage.LOG_FILE   = orig_log


@pytest.fixture
def api_client(robot_storage):
    """StorageをパッチしたFastAPI TestClientを返す。"""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)
