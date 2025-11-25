"""
Deployment Pydantic Schemas
Request/response models for deployment API endpoints
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class DeploymentStatusEnum(str, Enum):
    """Deployment status values"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"


class ReplicaStatusEnum(str, Enum):
    """Replica status values"""
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


# ============================================================================
# Request Schemas
# ============================================================================

class DeploymentResourceCreate(BaseModel):
    """Resource allocation for deployment creation"""
    cpu_cores: float = Field(ge=0.5, le=32, description="CPU cores (fractional allowed)")
    memory_mb: int = Field(ge=512, le=65536, description="Memory in MB")
    gpu_units: int = Field(ge=0, le=8, default=0, description="GPU units")
    storage_gb: int = Field(ge=1, le=1000, description="Storage in GB")


class DeploymentCreate(BaseModel):
    """Request to create a new deployment"""
    name: str = Field(min_length=1, max_length=100, description="Deployment name")
    container_image: str = Field(min_length=1, max_length=500, description="Container image (e.g., nginx:latest)")
    target_replicas: int = Field(ge=1, le=100, default=1, description="Number of replicas")
    resources: DeploymentResourceCreate = Field(description="Resource allocation")

    @validator('name')
    def validate_name(cls, v):
        """Validate deployment name format"""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Name must contain only alphanumeric characters, hyphens, and underscores')
        return v


class DeploymentUpdate(BaseModel):
    """Request to update an existing deployment"""
    target_replicas: Optional[int] = Field(None, ge=1, le=100, description="Update replica count")
    resources: Optional[DeploymentResourceCreate] = Field(None, description="Update resource allocation")


class DeploymentScale(BaseModel):
    """Request to scale a deployment"""
    target_replicas: int = Field(ge=0, le=100, description="Target number of replicas (0 to stop all)")


# ============================================================================
# Response Schemas
# ============================================================================

class DeploymentResourceResponse(BaseModel):
    """Resource allocation response"""
    id: str
    deployment_id: str
    cpu_cores: float
    memory_mb: int
    gpu_units: int
    storage_gb: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeploymentReplicaResponse(BaseModel):
    """Individual replica response"""
    id: str
    deployment_id: str
    node_id: Optional[str]
    status: ReplicaStatusEnum
    container_id: Optional[str]
    started_at: Optional[datetime]
    stopped_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class DeploymentStatusHistoryResponse(BaseModel):
    """Status change audit entry response"""
    id: str
    deployment_id: str
    old_status: str
    new_status: str
    changed_by: Optional[str]
    changed_at: datetime
    reason: Optional[str]

    class Config:
        from_attributes = True


class DeploymentResponse(BaseModel):
    """Full deployment response"""
    id: str
    name: str
    user_id: str
    container_image: str
    status: DeploymentStatusEnum
    target_replicas: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    resources: Optional[DeploymentResourceResponse]
    replicas: Optional[List[DeploymentReplicaResponse]]

    class Config:
        from_attributes = True


class DeploymentListResponse(BaseModel):
    """Summary deployment response for list endpoints"""
    id: str
    name: str
    status: DeploymentStatusEnum
    target_replicas: int
    running_replicas: int
    created_at: datetime
    updated_at: datetime


class DeploymentCreateResponse(BaseModel):
    """Response after creating a deployment"""
    success: bool
    deployment_id: str
    name: str
    status: DeploymentStatusEnum
    target_replicas: int
    message: str


class DeploymentOperationResponse(BaseModel):
    """Generic response for deployment operations (scale, stop, delete)"""
    success: bool
    deployment_id: str
    status: DeploymentStatusEnum
    message: str
