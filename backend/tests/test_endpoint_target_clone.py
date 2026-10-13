"""被测接口克隆。"""


def _create_target(client, name="克隆源接口"):
    resp = client.post(
        "/api/endpoint-targets",
        json={
            "name": name,
            "description": "原始描述",
            "endpoint_url": "https://example.com/api/chat",
            "transport_mode": "json",
            "authorization": "Bearer test-token",
            "request_body_template": '{"content": "{{user_input}}"}',
            "verify_ssl": False,
            "response_mapping": {
                "response_path": "choices.0.message.content",
                "custom_parser": "key_value_fields",
            },
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_clone_endpoint_target_copies_all_fields(client):
    source = _create_target(client)

    cloned = client.post(f"/api/endpoint-targets/{source['id']}/clone")
    assert cloned.status_code == 201
    body = cloned.json()

    assert body["id"] != source["id"]
    assert body["name"] == "克隆源接口 副本"
    assert body["endpoint_url"] == source["endpoint_url"]
    # 密钥不回显（脱敏），但有掩码说明克隆体确实带着鉴权配置
    assert body["authorization"] is None
    assert body["authorization_masked"]
    assert body["request_body_template"] == source["request_body_template"]
    assert body["verify_ssl"] is False
    assert body["response_mapping"]["response_path"] == "choices.0.message.content"
    assert body["response_mapping"]["custom_parser"] == "key_value_fields"

    # 源配置不受影响
    names = [t["name"] for t in client.get("/api/endpoint-targets").json()]
    assert "克隆源接口" in names
    assert "克隆源接口 副本" in names


def test_clone_endpoint_target_not_found(client):
    assert client.post("/api/endpoint-targets/999999/clone").status_code == 404
