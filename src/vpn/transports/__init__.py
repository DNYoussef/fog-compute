"""
VPN Transport Layer Implementations

This module provides various transport implementations for the VPN layer,
enabling flexible packet routing strategies.
"""

from .betanet_transport import BetanetTransport

__all__ = ["BetanetTransport"]
