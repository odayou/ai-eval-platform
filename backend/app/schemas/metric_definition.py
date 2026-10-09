from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, model_validator

# 自定义指标可选类型
ALLOWED_METRIC_TYPES = {
    "numeric",
    "discrete",
    "aspect_critic",
    "exact_match",
    "code_retrieval_hit_rate",
    "code_retrieval_mrr",
    "builtin_tool_call_accuracy",
    "builtin_argument_correctness",
    "builtin_step_efficiency",
}

# 内置指标类型前缀（builtin_faithfulness 等），同样允许出现在更新请求中
ALLOWED_METRIC_TYPE_PREFIXES = ("builtin_", "code_")


def is_allowed_metric_type(metric_type: str) -> bool:
    return metric_type in ALLOWED_METRIC_TYPES or metric_type.startswith(ALLOWED_METRIC_TYPE_PREFIXES)


class _MetricTypeValidator(BaseModel):
    metric_type: str
    config: Dict = {}

    @model_validator(mode="after")
    def validate_metric_type(self):
        metric_type = (self.metric_type or "").strip()
        if not is_allowed_metric_type(metric_type):
            raise ValueError(
                f"不支持的指标类型: {metric_type}；可选类型: {', '.join(sorted(ALLOWED_METRIC_TYPES))}"
            )
        if metric_type == "exact_match":
            config = self.config or {}
            if not str(config.get("field") or "").strip():
                raise ValueError("确定性匹配指标必须配置 config.field（待比对字段）")
            expected_field = str(config.get("expected_field") or "").strip()
            expected_value = config.get("expected_value")
            if not expected_field and expected_value in (None, ""):
                raise ValueError(
                    "确定性匹配指标必须配置 config.expected_field（期望值字段）或 config.expected_value（固定期望值）"
                )
        self.metric_type = metric_type
        return self


class MetricCreate(_MetricTypeValidator):
    name: str
    display_name: str
    category: str = "custom"


class MetricUpdate(_MetricTypeValidator):
    name: str
    display_name: str
    category: str = "custom"


class MetricResponse(BaseModel):
    id: int
    name: str
    display_name: str
    metric_type: str
    config: Optional[Dict] = None
    category: Optional[str] = None
    is_builtin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
