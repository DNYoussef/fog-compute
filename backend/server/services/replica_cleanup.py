"""
Replica lifecycle utilities for deployment operations.
"""
from datetime import datetime, timezone
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.deployment import DeploymentReplica, ReplicaStatus
from .docker_client import DockerClientError

logger = logging.getLogger(__name__)


async def stop_replica_for_deletion(
    replica: DeploymentReplica,
    db: AsyncSession,
    docker_client,
) -> None:
    """
    Stop and remove a replica's container during deployment deletion.

    Keeps status transitions consistent (STOPPING -> STOPPED) and logs Docker client
    errors without blocking deletion.
    """
    replica.status = ReplicaStatus.STOPPING
    await db.flush()  # Ensure intermediate state is visible

    if replica.container_id:
        try:
            await docker_client.stop_container(replica.container_id)
        except DockerClientError as e:
            logger.warning(
                f"Failed to stop container {replica.container_id} for replica {replica.id}: {e}"
            )
        except Exception as e:  # pragma: no cover - unexpected errors
            logger.warning(
                f"Unexpected error stopping container {replica.container_id} for replica {replica.id}: {e}"
            )

        try:
            await docker_client.remove_container(replica.container_id)
        except DockerClientError as e:
            logger.warning(
                f"Failed to remove container {replica.container_id} for replica {replica.id}: {e}"
            )
        except Exception as e:  # pragma: no cover - unexpected errors
            logger.warning(
                f"Unexpected error removing container {replica.container_id} for replica {replica.id}: {e}"
            )

    replica.status = ReplicaStatus.STOPPED
    replica.stopped_at = datetime.now(timezone.utc)
    replica.updated_at = datetime.now(timezone.utc)
