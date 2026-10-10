"""数据集与数据行的克隆。"""


def _create_dataset(client, name="克隆源"):
    resp = client.post(
        "/api/datasets",
        json={
            "name": name,
            "description": "用于克隆测试",
            "sample_type": "single_turn",
            "field_schema": [
                {"name": "user_input", "type": "text", "required": True, "description": "输入"},
                {"name": "expected_value", "type": "text", "required": False, "description": "期望值"},
            ],
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _add_row(client, dataset_id, data):
    resp = client.post(f"/api/datasets/{dataset_id}/rows", json={"data": data})
    assert resp.status_code == 201
    return resp.json()


def test_clone_dataset_copies_schema_and_rows(client):
    source = _create_dataset(client)
    _add_row(client, source["id"], {"user_input": "第一条", "expected_value": "装修需求"})
    _add_row(client, source["id"], {"user_input": "第二条", "expected_value": "未知"})

    cloned = client.post(f"/api/datasets/{source['id']}/clone", json={})
    assert cloned.status_code == 201
    body = cloned.json()

    assert body["id"] != source["id"]
    assert body["name"] == "克隆源 副本"
    assert body["row_count"] == 2
    assert [f["name"] for f in body["field_schema"]] == ["user_input", "expected_value"]

    rows = client.get(f"/api/datasets/{body['id']}/rows", params={"page": 1, "page_size": 50}).json()
    assert rows["total"] == 2
    assert rows["items"][0]["data"]["user_input"] == "第一条"
    # 行索引重新排布
    assert [item["row_index"] for item in rows["items"]] == [0, 1]

    # 原始数据不受影响
    original = client.get(f"/api/datasets/{source['id']}/rows", params={"page": 1, "page_size": 50}).json()
    assert original["total"] == 2


def test_clone_dataset_can_rename_and_skip_rows(client):
    source = _create_dataset(client, name="只克隆结构")
    _add_row(client, source["id"], {"user_input": "一条"})

    cloned = client.post(
        f"/api/datasets/{source['id']}/clone",
        json={"name": "空壳数据集", "include_rows": False},
    )
    assert cloned.status_code == 201
    body = cloned.json()

    assert body["name"] == "空壳数据集"
    assert body["row_count"] == 0
    rows = client.get(f"/api/datasets/{body['id']}/rows").json()
    assert rows["total"] == 0


def test_clone_dataset_not_found(client):
    assert client.post("/api/datasets/999999/clone", json={}).status_code == 404


def test_clone_row_appends_copy(client):
    source = _create_dataset(client, name="行克隆源")
    row = _add_row(client, source["id"], {"user_input": "原始行", "expected_value": "装修需求"})

    cloned_row = client.post(
        f"/api/datasets/{source['id']}/rows/{row['id']}/clone", json={"count": 1}
    )
    assert cloned_row.status_code == 201
    body = cloned_row.json()
    assert body["id"] != row["id"]
    assert body["data"] == row["data"]
    assert body["row_index"] == 1

    rows = client.get(f"/api/datasets/{source['id']}/rows", params={"page": 1, "page_size": 50}).json()
    assert rows["total"] == 2
    assert rows["items"][1]["data"]["user_input"] == "原始行"

    dataset = client.get(f"/api/datasets/{source['id']}").json()
    assert dataset["row_count"] == 2


def test_clone_row_multiple_copies(client):
    source = _create_dataset(client, name="批量克隆源")
    row = _add_row(client, source["id"], {"user_input": "模板行"})

    client.post(f"/api/datasets/{source['id']}/rows/{row['id']}/clone", json={"count": 3})

    rows = client.get(f"/api/datasets/{source['id']}/rows", params={"page": 1, "page_size": 50}).json()
    assert rows["total"] == 4
    assert [item["row_index"] for item in rows["items"]] == [0, 1, 2, 3]


def test_clone_row_not_found(client):
    source = _create_dataset(client, name="行克隆缺失")
    assert (
        client.post(f"/api/datasets/{source['id']}/rows/999999/clone", json={}).status_code == 404
    )
