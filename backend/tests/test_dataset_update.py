"""数据集编辑：改名/改描述，以及空数据集才能改字段结构。"""


def _create_dataset(client, name="待编辑", with_row=False):
    resp = client.post(
        "/api/datasets",
        json={
            "name": name,
            "description": "原始描述",
            "sample_type": "single_turn",
            "field_schema": [
                {"name": "user_input", "type": "text", "required": True, "description": "输入"},
            ],
        },
    )
    assert resp.status_code == 201
    dataset = resp.json()
    if with_row:
        row = client.post(
            f"/api/datasets/{dataset['id']}/rows",
            json={"data": {"user_input": "一条"}},
        )
        assert row.status_code == 201
    return dataset


def test_update_name_and_description(client):
    dataset = _create_dataset(client, name="旧名字")

    resp = client.put(
        f"/api/datasets/{dataset['id']}",
        json={"name": "新名字", "description": "新描述"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["name"] == "新名字"
    assert body["description"] == "新描述"
    # 未传 field_schema 时结构保持不变
    assert [f["name"] for f in body["field_schema"]] == ["user_input"]


def test_update_schema_allowed_when_empty(client):
    dataset = _create_dataset(client, name="空数据集可改结构")

    resp = client.put(
        f"/api/datasets/{dataset['id']}",
        json={
            "field_schema": [
                {"name": "user_input", "type": "text", "required": True, "description": "输入"},
                {"name": "expected_value", "type": "text", "required": False, "description": "期望值"},
            ]
        },
    )
    assert resp.status_code == 200
    assert [f["name"] for f in resp.json()["field_schema"]] == ["user_input", "expected_value"]


def test_update_schema_rejected_when_has_rows(client):
    dataset = _create_dataset(client, name="非空数据集", with_row=True)

    resp = client.put(
        f"/api/datasets/{dataset['id']}",
        json={
            "field_schema": [
                {"name": "user_input", "type": "text", "required": True, "description": "输入"},
                {"name": "brand_new", "type": "text", "required": False, "description": "新字段"},
            ]
        },
    )
    assert resp.status_code == 400
    assert "非空" in resp.json()["detail"]

    # 结构未被改动
    current = client.get(f"/api/datasets/{dataset['id']}").json()
    assert [f["name"] for f in current["field_schema"]] == ["user_input"]


def test_update_name_still_works_when_has_rows(client):
    """有数据行时仍允许改名/改描述。"""

    dataset = _create_dataset(client, name="有数据的旧名", with_row=True)

    resp = client.put(
        f"/api/datasets/{dataset['id']}", json={"name": "有数据的新名"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "有数据的新名"


def test_update_not_found(client):
    assert client.put("/api/datasets/999999", json={"name": "x"}).status_code == 404
