from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.metric_kinds import metric_needs_llm


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    metric_type = Column(String(50), nullable=False)
    config = Column(JSON, nullable=True)
    category = Column(String(100), nullable=True)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    @property
    def needs_llm(self) -> bool:
        """是否需要 Judge 大模型；由 app.core.metric_kinds 统一判定并下发给前端。"""

        return metric_needs_llm(self.metric_type, self.name)
