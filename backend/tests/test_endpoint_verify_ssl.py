"""被测接口的 TLS 校验开关（verify_ssl）。"""

import httpx
import pytest

from app.core import endpoint_eval
from app.core.endpoint_eval import invoke_endpoint


@pytest.mark.asyncio
async def test_verify_ssl_false_disables_certificate_check(monkeypatch):
    captured: dict = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            raise RuntimeError("should not be reached")

    monkeypatch.setattr(endpoint_eval.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(Exception):
        await invoke_endpoint(
            {"user_input": "hi"},
            {
                "endpoint_url": "https://internal.example.com/chat",
                "request_body_template": "{}",
                "verify_ssl": False,
            },
        )

    assert captured.get("verify") is False


@pytest.mark.asyncio
async def test_verify_ssl_defaults_to_true(monkeypatch):
    captured: dict = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            raise RuntimeError("should not be reached")

    monkeypatch.setattr(endpoint_eval.httpx, "AsyncClient", _FakeClient)

    with pytest.raises(Exception):
        await invoke_endpoint(
            {"user_input": "hi"},
            {"endpoint_url": "https://example.com/chat", "request_body_template": "{}"},
        )

    assert captured.get("verify") is True


def test_endpoint_target_persists_verify_ssl(client):
    created = client.post(
        "/api/endpoint-targets",
        json={
            "name": "内网接口",
            "endpoint_url": "https://internal.example.com/chat",
            "request_body_template": "{}",
            "verify_ssl": False,
        },
    )
    assert created.status_code == 201
    assert created.json()["verify_ssl"] is False

    target_id = created.json()["id"]
    listed = client.get("/api/endpoint-targets").json()
    assert next(item["id"] == target_id and item["verify_ssl"] is False for item in listed)

    # 未传该字段时默认开启校验
    defaulted = client.post(
        "/api/endpoint-targets",
        json={
            "name": "公网接口",
            "endpoint_url": "https://api.example.com/chat",
            "request_body_template": "{}",
        },
    )
    assert defaulted.status_code == 201
    assert defaulted.json()["verify_ssl"] is True
