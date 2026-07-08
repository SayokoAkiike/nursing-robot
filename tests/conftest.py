import os

import pytest

os.environ.setdefault("NURSE_TOKEN", "precare-dev-token-2026")

from backend.db import session as db_session

NURSE_TOKEN = "precare-dev-token-2026"
HEADERS = {"x-nurse-token": NURSE_TOKEN}


@pytest.fixture
def robot_storage(tmp_path):
    """各テストで独立したSQLiteファイルを使う。

    PR1まではJSONファイル（STATE_FILE/LOG_FILE）を差し替えていたのと同じ考え
    方で、PR2からはSQLAlchemyのエンジンをテストごとに独立したSQLiteファイル
    に差し替える。
    """
    db_session.configure_engine(f"sqlite:///{tmp_path}/test.db")
    yield db_session
    db_session.configure_engine()  # 次のテスト/モジュールのためにデフォルトへ戻す


@pytest.fixture
def api_client(robot_storage):
    """DBをテスト用に差し替えたFastAPI TestClientを返す。"""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)

