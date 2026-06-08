"""
Pipeline Task Distribution
FOG-006: Distributed AI Execution Pipeline

Orchestrates multi-stage task pipelines across fog compute nodes.
Supports AI workloads with intelligent load balancing and failure recovery.
"""
from .models import (
    Pipeline,
    PipelineStage,
    PipelineStatus,
    StageStatus,
    TaskExecutionStatus,
    PipelineTask,
    PipelineDependency,
    DependencyType,
)
from .scheduler import PipelineScheduler, SchedulerConfig
from .distributor import TaskDistributor, DistributionStrategy, LoadBalancer
from .ai_handlers import (
    AIInferenceHandler,
    DataPreprocessHandler,
    ModelDownloadHandler,
)

__all__ = [
    # Models
    "Pipeline",
    "PipelineStage",
    "PipelineStatus",
    "StageStatus",
    "TaskExecutionStatus",
    "PipelineTask",
    "PipelineDependency",
    "DependencyType",
    # Scheduler
    "PipelineScheduler",
    "SchedulerConfig",
    # Distributor
    "TaskDistributor",
    "DistributionStrategy",
    "LoadBalancer",
    # AI Handlers
    "AIInferenceHandler",
    "DataPreprocessHandler",
    "ModelDownloadHandler",
]

__version__ = "0.1.0"
