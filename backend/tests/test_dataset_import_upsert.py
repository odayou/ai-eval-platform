"""导入的 id 语义：导出文件里的 id 命中本数据集则更新该行，否则新增。"""

import json

from tests.test_dataset import _create_dataset


def _add_row(client, dataset_id, data):
    resp = client.post(f"/api/datasets/{dataset_id}/rows", json={"data": data})
    assert resp.status_code == 201
    return resp.json()


def _export_json(client, dataset_id):
    resp = client.get(f"/api/datasets/{dataset_id}/export?format=json")
    assert resp.status_code == 200
    return json.loads(resp.content.decode("utf-8"))


def _import_json(client, dataset_id, records):
    content = json.dumps(records, ensure_ascii=False).encode()
    files = {"file": ("import.json", content, "application/json")}
    return client.post(f"/api/datasets/{dataset_id}/import", files=files)


def test_import_with_matching_id_updates_row(client):
    dataset = _create_dataset(client).json()
    row = _add_row(client, dataset["id"], {"user_input": "旧问题", "expected_value": "装修需求"})

    # 导出 → 修改内容 → 导回同一数据集
    records = _export_json(client, dataset["id"])
    records[0]["user_input"] = "离线修改后的问题"
    records[0]["expected_value"] = "室外装修"

    resp = _import_json(client, dataset["id"], records)
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1
    assert resp.json()["imported_count"] == 0

    # 原行被就地更新：id 与位置不变
    rows = client.get(f"/api/datasets/{dataset['id']}/rows").json()
    assert rows["total"] == 1
    assert rows["items"][0]["id"] == row["id"]
    assert rows["items"][0]["row_index"] == row["row_index"]
    assert rows["items"][0]["data"]["user_input"] == "离线修改后的问题"
    # id 列不进入 data
    assert "id" not in rows["items"][0]["data"]


def test_import_with_unknown_id_imports_as_new_row(client):
    dataset = _create_dataset(client).json()

    records = [{"id": 99999, "user_input": "新样本", "expected_value": "未知"}]
    resp = _import_json(client, dataset["id"], records)
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 0
    assert resp.json()["imported_count"] == 1

    rows = client.get(f"/api/datasets/{dataset['id']}/rows").json()
    assert rows["total"] == 1
    assert rows["items"][0]["id"] != 99999
    assert "id" not in rows["items"][0]["data"]


def test_import_without_id_still_deduplicates(client):
    """不带 id 的导入走原有内容去重逻辑，行为不变。"""

    dataset = _create_dataset(client).json()
    _add_row(client, dataset["id"], {"user_input": "已有问题"})

    records = [
        {"user_input": "已有问题"},
        {"user_input": "新问题"},
    ]
    resp = _import_json(client, dataset["id"], records)
    assert resp.json()["skipped_duplicates"] == 1
    assert resp.json()["imported_count"] == 1
    assert resp.json()["updated_count"] == 0


def test_import_id_respects_user_defined_id_field(client):
    """数据集字段里真的定义了 id 时，那是用户数据列，保留且不参与行定位。"""

    resp = client.post(
        "/api/datasets",
        json={
            "name": "自带id列的数据集",
            "description": "",
            "sample_type": "single_turn",
            "field_schema": [
                {"name": "id", "type": "text", "required": False, "description": "业务编号"},
                {"name": "user_input", "type": "text", "required": True, "description": "输入"},
            ],
        },
    )
    assert resp.status_code == 201
    dataset = resp.json()

    records = [{"id": "SKU-001", "user_input": "问题"}]
    resp = _import_json(client, dataset["id"], records)
    assert resp.status_code == 200
    assert resp.json()["imported_count"] == 1

    rows = client.get(f"/api/datasets/{dataset['id']}/rows").json()
    assert rows["items"][0]["data"]["id"] == "SKU-001"


def test_export_import_roundtrip_identities_stable(client):
    """完整往返：导出→改一条→加一条→导入，被改的行 id 不变，新增行拿新 id。"""

    dataset = _create_dataset(client).json()
    row_a = _add_row(client, dataset["id"], {"user_input": "问题A"})
    _add_row(client, dataset["id"], {"user_input": "问题B"})

    records = _export_json(client, dataset["id"])
    records[0]["user_input"] = "问题A-改"
    records.append({"id": None, "user_input": "问题C"})
    # 去掉 None id，模拟新行没有 id
    records[-1].pop("id")

    resp = _import_json(client, dataset["id"], records)
    assert resp.json()["updated_count"] == 1
    assert resp.json()["imported_count"] == 1

    rows = client.get(f"/api/datasets/{dataset['id']}/rows").json()
    by_id = {r["id"]: r for r in rows["items"]}
    assert by_id[row_a["id"]]["data"]["user_input"] == "问题A-改"
    assert rows["total"] == 3
