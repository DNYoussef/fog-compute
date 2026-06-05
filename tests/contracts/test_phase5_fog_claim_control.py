"""Phase 5 claim-control tests for fog-compute public surfaces."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "backend"))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ALLOW_MOCKS", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-phase5-fog-claim-control")


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_demotes_mobile_mixnet_onion_and_tokenomics_claims():
    readme = _read("README.md")

    forbidden = [
        "Complete distributed fog computing system",
        "Mobile device compute collection during charging",
        "Cross-platform support (Android/iOS/Desktop)",
        "Mixnet integration for anonymity",
        "Fog-native onion coordination",
        "Market-based resource pricing",
        "Token staking and rewards",
        "Dynamic resource pricing based on demand",
    ]
    for phrase in forbidden:
        assert phrase not in readme

    required = [
        "Native mobile bridge is not implemented",
        "Nym mixnet: not implemented",
        "Onion consensus: simulated in development",
        "Token market cap/APR: unavailable",
    ]
    for phrase in required:
        assert phrase in readme


@pytest.mark.asyncio
async def test_mixnet_stats_report_not_implemented():
    from vpn.fog_onion_coordinator import MIXNET_AVAILABLE, NymMixnetClient

    client = NymMixnetClient(client_id="claim-control")
    stats = await client.get_mixnet_stats()

    assert MIXNET_AVAILABLE is False
    assert stats["mixnet_available"] is False
    assert stats["stub_implementation"] is True
    assert stats["evidence_status"] == "not_implemented"
    assert stats["production_ready"] is False


@pytest.mark.asyncio
async def test_onion_consensus_is_labeled_simulated_not_directory_authority():
    from vpn.onion_routing import NodeType, OnionRouter

    router = OnionRouter(node_id="claim-control", node_types={NodeType.MIDDLE})
    assert await router.fetch_consensus() is True

    stats = router.get_stats()
    assert stats["consensus_simulated"] is True
    assert stats["directory_authority_status"] == "simulated_development_only"
    assert stats["consensus_evidence_status"] == "simulated_not_directory_authority"
    assert stats["production_anonymity_claimed"] is False


def test_mobile_bridge_reports_not_implemented_when_requested():
    from p2p.unified_p2p_system import UnifiedDecentralizedSystem

    system = UnifiedDecentralizedSystem(
        node_id="mobile-claim-control",
        enable_bitchat=False,
        enable_betanet=False,
        enable_mobile_bridge=True,
    )

    status = system.get_status()
    assert status["mobile_bridge_requested"] is True
    assert status["mobile_bridge_available"] is False
    assert status["mobile_bridge_status"] == "not_implemented"


def test_control_panel_tokenomics_has_no_fabricated_market_claims():
    page = _read("apps/control-panel/app/tokenomics/page.tsx")
    api_route = _read("apps/control-panel/app/api/tokenomics/stats/route.ts")

    forbidden = [
        "+12.5% 24h",
        "High demand for GPU compute - prices up 8% this week",
        "Earn 12% APY",
        "Reduce marketplace fees to 1%",
        "Total Value Locked",
        "marketCap: 0",
        "stakingAPR: 0",
    ]
    combined = page + "\n" + api_route
    for phrase in forbidden:
        assert phrase not in combined

    assert "No live price feed configured" in page
    assert "Live marketplace trend feed is not configured" in page
    assert "marketCap: null" in api_route
    assert "stakingAPR: null" in api_route


def test_deployment_deletion_contract_file_has_real_assertions():
    source = _read("tests/test_deployment_deletion.py")

    assert "TO" + "DO" not in source
    assert "ast.Pass" in source
    assert "assert response[\"success\"] is True" in source
