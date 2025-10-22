"""
Input Validation Schemas
Pydantic models for request body validation and sanitization
"""
from pydantic import BaseModel, Field, validator, constr, conint, confloat
from typing import Optional, List
from datetime import datetime
import html


class JobSubmitSchema(BaseModel):
    """
    Schema for job submission
    Validates and sanitizes job creation requests
    """
    name: constr(min_length=1, max_length=200) = Field(..., description="Job name")
    sla_tier: str = Field(..., description="SLA tier: bronze, silver, gold, platinum")
    cpu_required: confloat(ge=0.0, le=64.0) = Field(..., description="CPU cores required")
    memory_required: confloat(ge=0.0, le=512.0) = Field(..., description="Memory in GB")
    gpu_required: confloat(ge=0.0, le=8.0) = Field(0.0, description="GPU count required")
    duration_estimate: Optional[confloat(ge=0.0)] = Field(None, description="Estimated duration in minutes")
    data_size_mb: Optional[confloat(ge=0.0)] = Field(None, description="Data size in MB")

    @validator('name')
    def sanitize_name(cls, v):
        """Sanitize job name to prevent XSS"""
        return html.escape(v.strip())

    @validator('sla_tier')
    def validate_sla(cls, v):
        """Ensure SLA tier is valid"""
        valid_tiers = ['bronze', 'silver', 'gold', 'platinum']
        v_lower = v.lower()
        if v_lower not in valid_tiers:
            raise ValueError(f'SLA tier must be one of: {", ".join(valid_tiers)}')
        return v_lower


class DeviceRegisterSchema(BaseModel):
    """
    Schema for device registration
    Validates idle compute device details
    """
    device_id: constr(min_length=1, max_length=255) = Field(..., description="Unique device identifier")
    device_type: str = Field(..., description="Device type: android, ios, desktop")
    cpu_cores: conint(ge=1, le=128) = Field(..., description="Number of CPU cores")
    memory_mb: conint(ge=512, le=524288) = Field(..., description="Memory in MB")
    battery_percent: Optional[confloat(ge=0.0, le=100.0)] = Field(100.0, description="Battery percentage")
    is_charging: Optional[bool] = Field(False, description="Is device charging")

    @validator('device_type')
    def validate_device_type(cls, v):
        """Ensure device type is valid"""
        valid_types = ['android', 'ios', 'desktop', 'laptop', 'edge']
        v_lower = v.lower()
        if v_lower not in valid_types:
            raise ValueError(f'Device type must be one of: {", ".join(valid_types)}')
        return v_lower


class TokenTransferSchema(BaseModel):
    """
    Schema for token transfer
    Validates tokenomics transactions
    """
    from_address: constr(pattern=r'^0x[a-fA-F0-9]{64}$') = Field(..., description="Source wallet address")
    to_address: constr(pattern=r'^0x[a-fA-F0-9]{64}$') = Field(..., description="Destination wallet address")
    amount: confloat(gt=0.0) = Field(..., description="Amount to transfer")

    @validator('to_address')
    def validate_not_same_address(cls, v, values):
        """Ensure source and destination are different"""
        if 'from_address' in values and v == values['from_address']:
            raise ValueError('Cannot transfer to the same address')
        return v


class StakeSchema(BaseModel):
    """
    Schema for token staking
    Validates staking operations
    """
    address: constr(pattern=r'^0x[a-fA-F0-9]{64}$') = Field(..., description="Wallet address")
    amount: confloat(gt=0.0) = Field(..., description="Amount to stake")


class ProposalSchema(BaseModel):
    """
    Schema for DAO proposal creation
    Validates governance proposals
    """
    title: constr(min_length=10, max_length=200) = Field(..., description="Proposal title")
    description: constr(min_length=50, max_length=5000) = Field(..., description="Proposal description")
    proposer: constr(pattern=r'^0x[a-fA-F0-9]{64}$') = Field(..., description="Proposer wallet address")

    @validator('title', 'description')
    def sanitize_text(cls, v):
        """Sanitize text fields to prevent XSS"""
        return html.escape(v.strip())
