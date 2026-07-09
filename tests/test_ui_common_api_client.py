"""Tests for the two PR26 additions to ui/common/api_client.py.

Mocks `requests` (no real HTTP call, no backend needed) -- same
lightweight approach as testing any other thin HTTP wrapper in this repo
(perception/verification_client.py's own tests use httpx's ASGI
transport instead since that module supports it; api_client.py is a much
simpler `requests`-based module with no such in-process mode, so a mock
is the natural fit here).
"""
from unittest.mock import MagicMock, patch

from ui.common import api_client


def _mock_response(json_body):
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


@patch("ui.common.api_client.requests.get")
def test_get_escalations_no_status_filter(mock_get):
    mock_get.return_value = _mock_response([{"id": "esc-1", "status": "PENDING"}])
    result = api_client.get_escalations()
    assert result == [{"id": "esc-1", "status": "PENDING"}]
    args, kwargs = mock_get.call_args
    assert args[0].endswith("/escalations")
    assert kwargs["params"] is None


@patch("ui.common.api_client.requests.get")
def test_get_escalations_with_status_filter(mock_get):
    mock_get.return_value = _mock_response([])
    api_client.get_escalations(status="PENDING")
    _args, kwargs = mock_get.call_args
    assert kwargs["params"] == {"status": "PENDING"}


@patch("ui.common.api_client.requests.post")
def test_acknowledge_escalation_sends_nurse_headers(mock_post):
    mock_post.return_value = _mock_response({"escalation": {"status": "ACKNOWLEDGED"}})
    result = api_client.acknowledge_escalation("esc-1", "nurse_demo")
    assert result == {"escalation": {"status": "ACKNOWLEDGED"}}
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/escalations/esc-1/ack")
    assert "x-nurse-token" in kwargs["headers"]
    assert kwargs["json"] == {"acknowledged_by": "nurse_demo"}
