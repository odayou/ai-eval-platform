from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class EvalScenario(Base):
    __tablename__ = "eval_scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    scene_type = Column(String(50), nullable=False)
    sample_type = Column(String(50), default="single_turn")
    is_preset = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    metrics = relationship("ScenarioMetric", back_populates="scenario", cascade="all, delete-orphan")

    @property
    def needs_llm(self) -> bool:
        """场景是否需要 Judge 大模型：任一指标需要即为需要。"""

        return any(
            scenario_metric.metric_definition.needs_llm
            for scenario_metric in (self.metrics or [])
            if scenario_metric.metric_definition is not None
        )


class ScenarioMetric(Base):
    __tablename__ = "scenario_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey("eval_scenarios.id", ondelete="CASCADE"), nullable=False)
    metric_definition_id = Column(Integer, ForeignKey("metric_definitions.id"), nullable=False)
    weight = Column(Float, default=1.0)
    pass_threshold = Column(Float, nullable=True)
    prompt_override = Column(Text, nullable=True)

    scenario = relationship("EvalScenario", back_populates="metrics")
    metric_definition = relationship("MetricDefinition")
