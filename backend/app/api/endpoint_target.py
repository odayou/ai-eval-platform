from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.endpoint_eval import extract_eval_fields, invoke_endpoint, parse_json_loose
from app.core.parser_loader import (
    delete_parser,
    get_parser,
    list_parsers,
    read_parser_code,
    run_parser_code,
    save_parser,
)
from app.models.endpoint_target import EndpointTarget
from app.schemas.endpoint_target import (
    CustomParserSaveRequest,
    CustomParserTestRequest,
    CustomParserTestResponse,
    CustomParserUpdateRequest,
    EndpointTargetCreate,
    EndpointTargetResponse,
    EndpointTargetTestRequest,
    EndpointTargetTestResponse,
    EndpointTargetUpdate,
)

router = APIRouter(prefix="/endpoint-targets", tags=["Endpoint Targets"])


@router.get("/parsers")
def list_custom_parsers():
    """列出可用的自定义响应解析器（backend/custom_parsers/ 目录下的插件）。"""
    return list_parsers()


@router.get("/parsers/{name}")
def get_custom_parser(name: str):
    code = read_parser_code(name)
    if code is None:
        raise HTTPException(status_code=404, detail="解析器不存在")
    parsers = {p["name"]: p for p in list_parsers()}
    return {"name": name, "description": parsers.get(name, {}).get("description", ""), "code": code}


@router.post("/parsers", status_code=201)
def create_custom_parser(payload: CustomParserSaveRequest):
    try:
        save_parser(payload.name.strip(), payload.code, overwrite=False)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="解析器已存在，请直接编辑")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"name": payload.name.strip()}


@router.put("/parsers/{name}", status_code=200)
def update_custom_parser(name: str, payload: CustomParserUpdateRequest):
    try:
        save_parser(name, payload.code, overwrite=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"name": name}


@router.delete("/parsers/{name}", status_code=204)
def delete_custom_parser(name: str):
    try:
        delete_parser(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="解析器不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return None


@router.post("/parsers/test", response_model=CustomParserTestResponse)
def test_custom_parser(payload: CustomParserTestRequest):
    """在线试解析：优先使用草稿代码，否则按名称加载已保存的解析器。"""
    parsed = parse_json_loose(payload.parsed_response) if payload.parsed_response else None
    try:
        if payload.code and payload.code.strip():
            result = run_parser_code(payload.code, payload.raw_text, parsed, {})
        else:
            parser = get_parser(payload.name or "")
            if parser is None:
                return CustomParserTestResponse(success=False, error=f"解析器不存在: {payload.name}")
            result = parser(payload.raw_text, parsed, {})
        if isinstance(result, dict):
            result = {str(k): v for k, v in result.items() if v is not None}
        return CustomParserTestResponse(success=True, result=result)
    except Exception as exc:
        return CustomParserTestResponse(success=False, error=str(exc))


def _target_config(target: EndpointTarget) -> dict:
    return {
        "endpoint_url": target.endpoint_url,
        "transport_mode": target.transport_mode or "json",
        "authorization": target.authorization or "",
        "extra_headers": target.extra_headers or "{}",
        "request_body_template": target.request_body_template or "",
        "verify_ssl": target.verify_ssl is not False,
    }


def _get_target_or_404(target_id: int, db: Session) -> EndpointTarget:
    target = db.query(EndpointTarget).filter(EndpointTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Endpoint target not found")
    return target


@router.get("", response_model=List[EndpointTargetResponse])
def list_endpoint_targets(db: Session = Depends(get_db)):
    return db.query(EndpointTarget).order_by(EndpointTarget.created_at.desc()).all()


@router.post("", response_model=EndpointTargetResponse, status_code=201)
def create_endpoint_target(payload: EndpointTargetCreate, db: Session = Depends(get_db)):
    if not payload.endpoint_url.strip():
        raise HTTPException(status_code=400, detail="endpoint_url is required")
    target = EndpointTarget(**payload.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


@router.put("/{target_id}", response_model=EndpointTargetResponse)
def update_endpoint_target(
    target_id: int,
    payload: EndpointTargetUpdate,
    db: Session = Depends(get_db),
):
    target = _get_target_or_404(target_id, db)
    data = payload.model_dump(exclude_unset=True)
    if "endpoint_url" in data and not str(data["endpoint_url"] or "").strip():
        raise HTTPException(status_code=400, detail="endpoint_url is required")
    if "authorization" in data and not str(data["authorization"] or "").strip():
        data.pop("authorization")
    for key, value in data.items():
        setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return target


@router.delete("/{target_id}", status_code=204)
def delete_endpoint_target(target_id: int, db: Session = Depends(get_db)):
    target = _get_target_or_404(target_id, db)
    db.delete(target)
    db.commit()
    return None


@router.post("/{target_id}/test", response_model=EndpointTargetTestResponse)
async def test_endpoint_target(
    target_id: int,
    payload: EndpointTargetTestRequest,
    db: Session = Depends(get_db),
):
    target = _get_target_or_404(target_id, db)
    try:
        response_payload = await invoke_endpoint(payload.row_data or {}, _target_config(target))
        extracted_fields, mapping_errors = extract_eval_fields(
            response_payload,
            target.response_mapping or {},
        )
        return EndpointTargetTestResponse(
            success=True,
            message="接口调用成功",
            request_body=response_payload.get("request_body"),
            status_code=response_payload.get("status_code"),
            latency_ms=response_payload.get("latency_ms"),
            raw_response=response_payload.get("raw_response"),
            extracted_fields=extracted_fields,
            mapping_errors=mapping_errors,
        )
    except Exception as exc:
        return EndpointTargetTestResponse(success=False, message=str(exc))
