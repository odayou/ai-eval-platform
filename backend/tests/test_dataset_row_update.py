"""数据集单行编辑。"""


def _create_dataset(client, name="行编辑数据集"):
    resp = client.post(
        "/api/datasets",
        json={
            "name": name,
            "description": "",
            "sample_type": "single_turn",
            "field_schema": [
                {"name": "user_input", "type": "text", "required": True, "description": "输入"},
                {"name": "expected_value", "type": "text", "required": False, "description": "期望值"},
                {"name": "tags", "type": "text_list", "required": False, "description": "标签"},
            ],
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _add_row(client, dataset_id, data):
    resp = client.post(f"/api/datasets/{dataset_id}/rows", json={"data": data})
    assert resp.status_code == 201
    return resp.json()


def test_update_row_data(client):
    dataset = _create_dataset(client)
    row = _add_row(client, dataset["id"], {"user_input": "原始问题", "expected_value": "装修需求"})

    resp = client.put(
        f"/api/datasets/{dataset['id']}/rows/{row['id']}",
        json={"data": {"user_input": "修改后的问题", "expected_value": "室外装修"}},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["user_input"] == "修改后的问题"
    assert resp.json()["data"]["expected_value"] == "室外装修"
    assert resp.json()["id"] == row["id"]
    assert resp.json()["row_index"] == row["row_index"]


def test_update_row_normalizes_json_text_fields(client):
    """编辑器里 JSON 字段以文本提交，后端应按字段类型还原为结构化值。"""

    dataset = _create_dataset(client)
    row = _add_row(client, dataset["id"], {"user_input": "问题"})

    resp = client.put(
        f"/api/datasets/{dataset['id']}/rows/{row['id']}",
        json={"data": {"user_input": "问题", "tags": '["标签A", "标签B"]'}},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["tags"] == ["标签A", "标签B"]


def test_update_row_rejects_missing_required_field(client):
    dataset = _create_dataset(client)
    row = _add_row(client, dataset["id"], {"user_input": "问题"})

    resp = client.put(
        f"/api/datasets/{dataset['id']}/rows/{row['id']}",
        json={"data": {"expected_value": "缺了必填项"}},
    )
    assert resp.status_code == 422

    # 原数据未被破坏
    rows = client.get(f"/api/datasets/{dataset['id']}/rows").json()
    assert rows["items"][0]["data"]["user_input"] == "问题"


def test_update_row_not_found(client):
    dataset = _create_dataset(client)

    assert (
        client.put(
            f"/api/datasets/{dataset['id']}/rows/999999",
            json={"data": {"user_input": "x"}},
        ).status_code
        == 404
    )


def test_update_row_cannot_modify_row_of_another_dataset(client):
    ds_a = _create_dataset(client, name="数据集A")
    ds_b = _create_dataset(client, name="数据集B")
    row = _add_row(client, ds_a["id"], {"user_input": "问题"})

    resp = client.put(
        f"/api/datasets/{ds_b['id']}/rows/{row['id']}",
        json={"data": {"user_input": "越权修改"}},
    )
    assert resp.status_code == 404


def test_private_network_origin_allowed_by_cors(client):
    """通过局域网 IP 打开前端时，/api 请求不应被 CORS 拒绝。"""

    resp = client.get(
        "/api/health",
        headers={"Origin": "http://10.4.21.46:5173"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://10.4.21.46:5173"
