import json

import pytest

from vpn.fog_onion_coordinator import FogOnionCoordinator, PrivacyAwareTask, PrivacyLevel


@pytest.mark.asyncio
async def test_privacy_task_serialization_is_json_not_pickle():
    coordinator = FogOnionCoordinator(
        node_id="node-a",
        fog_coordinator=object(),
        enable_mixnet=False,
    )
    task = PrivacyAwareTask(
        task_id="task-1",
        privacy_level=PrivacyLevel.PRIVATE,
        task_data=b"payload",
        compute_requirements={"cpu": 1},
        client_id="client-1",
    )

    serialized = await coordinator._serialize_task(task)

    assert not serialized.startswith(b"\x80")
    payload = json.loads(serialized.decode("utf-8"))
    assert payload == {
        "format_version": 1,
        "task_id": "task-1",
        "privacy_level": "private",
        "task_data_b64": "cGF5bG9hZA==",
        "compute_requirements": {"cpu": 1},
        "client_id": "client-1",
    }
