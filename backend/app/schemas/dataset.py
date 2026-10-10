from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class FieldDefinition(BaseModel):
    name: str
    type: str  # text / number / text_list / conversation / tool_call_list / tags / json
    required: bool = False
    description: str = ""


class DatasetCreate(BaseModel):
    name: str
    description: str = ""
    sample_type: str
    field_schema: List[FieldDefinition]


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    # 仅在数据集为空（row_count == 0）时允许修改，避免历史行数据与新结构不兼容
    field_schema: Optional[List[FieldDefinition]] = None


class DatasetCloneRequest(BaseModel):
    """克隆数据集：默认连同行数据一起复制。"""

    name: Optional[str] = None
    include_rows: bool = True


class DatasetRowCloneRequest(BaseModel):
    """克隆数据行，可一次复制多份（用于快速造批量样本）。"""

    count: int = 1


class DatasetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    sample_type: str
    field_schema: Optional[List[FieldDefinition]] = None
    row_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetRowCreate(BaseModel):
    data: Dict[str, Any]


class DatasetRowResponse(BaseModel):
    id: int
    dataset_id: int
    row_index: int
    data: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetRowsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[DatasetRowResponse]
