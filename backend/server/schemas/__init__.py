"""
Pydantic Schemas for Request/Response Validation
Ensures type safety and data validation across all API endpoints
"""
from .auth import UserCreate, UserLogin, UserResponse, Token, TokenData
from .validation import (
    JobSubmitSchema,
    DeviceRegisterSchema,
    TokenTransferSchema,
    StakeSchema,
    ProposalSchema,
)
from .deployment import (
    DeploymentCreate,
    DeploymentUpdate,
    DeploymentScale,
    DeploymentResponse,
    DeploymentListResponse,
    DeploymentCreateResponse,
    DeploymentOperationResponse,
    DeploymentResourceCreate,
    DeploymentResourceResponse,
    DeploymentReplicaResponse,
    DeploymentStatusHistoryResponse,
    DeploymentStatusEnum,
    ReplicaStatusEnum,
)

__all__ = [
    # Auth schemas
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "Token",
    "TokenData",
    # Validation schemas
    "JobSubmitSchema",
    "DeviceRegisterSchema",
    "TokenTransferSchema",
    "StakeSchema",
    "ProposalSchema",
    # Deployment schemas
    "DeploymentCreate",
    "DeploymentUpdate",
    "DeploymentScale",
    "DeploymentResponse",
    "DeploymentListResponse",
    "DeploymentCreateResponse",
    "DeploymentOperationResponse",
    "DeploymentResourceCreate",
    "DeploymentResourceResponse",
    "DeploymentReplicaResponse",
    "DeploymentStatusHistoryResponse",
    "DeploymentStatusEnum",
    "ReplicaStatusEnum",
]
