"""
Comprehensive WebSocket Tests
Tests WebSocket server, publishers, and metrics aggregation
"""
import pytest
import asyncio
from fastapi import WebSocket
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
from datetime import datetime

from tests.constants import (
    TEST_CONNECTIONS_SMALL,
    TEST_CONNECTIONS_LARGE,
    TEST_ROOM_NAME,
    TEST_ROOM_CONNECTIONS,
    TEST_BROADCAST_CONNECTIONS,
    TEST_PUBLISHER_COUNT,
    TEST_MIN_MESSAGE_COUNT,
    TEST_WINDOW_SECONDS,
    TEST_MAX_WINDOW_POINTS,
    TEST_SLEEP_MEDIUM,
)
from server.websocket.server import ConnectionManager, connection_manager
from server.websocket.publishers import (
    DataPublisher, NodeStatusPublisher, TaskProgressPublisher,
    MetricsPublisher, AlertPublisher, ResourcePublisher,
    TopologyPublisher, PublisherManager
)
from server.services.metrics_aggregator import (
    MetricAggregator, TimeSeriesWindow, AnomalyDetector
)


class TestConnectionManager:
    """Test WebSocket connection management"""

    @pytest.fixture
    async def manager(self):
        """Create a fresh connection manager"""
        manager = ConnectionManager()
        await manager.start()
        yield manager
        await manager.stop()

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket"""
        ws = AsyncMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, manager, mock_websocket):
        """Test: WebSocket connection lifecycle (connect -> disconnect)"""
        connection_id = "test-connection-1"

        # Connect
        await manager.connect(mock_websocket, connection_id, user_id="test-user")

        assert connection_id in manager.active_connections
        assert manager.stats["active_connections"] == 1
        assert manager.stats["total_connections"] == 1
        mock_websocket.accept.assert_called_once()

        # Disconnect
        await manager.disconnect(connection_id)

        assert connection_id not in manager.active_connections
        assert manager.stats["active_connections"] == 0
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_connections(self, manager):
        """Test: Handle multiple concurrent connections"""
        connections = []

        # Create TEST_CONNECTIONS_SMALL connections
        for i in range(TEST_CONNECTIONS_SMALL):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            connection_id = f"connection-{i}"
            await manager.connect(ws, connection_id)
            connections.append((connection_id, ws))

        assert len(manager.active_connections) == TEST_CONNECTIONS_SMALL
        assert manager.stats["active_connections"] == TEST_CONNECTIONS_SMALL

        # Disconnect all
        for connection_id, ws in connections:
            await manager.disconnect(connection_id)

        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_room_subscription(self, manager, mock_websocket):
        """Test: Room subscription and unsubscription"""
        connection_id = "test-connection"
        room = TEST_ROOM_NAME

        await manager.connect(mock_websocket, connection_id)

        # Subscribe
        await manager.subscribe_to_room(connection_id, room)

        assert connection_id in manager.rooms[room]
        assert room in manager.connection_metadata[connection_id]["subscribed_rooms"]

        # Unsubscribe
        await manager.unsubscribe_from_room(connection_id, room)

        assert connection_id not in manager.rooms[room]
        assert room not in manager.connection_metadata[connection_id]["subscribed_rooms"]

    @pytest.mark.asyncio
    async def test_personal_message(self, manager, mock_websocket):
        """Test: Send personal message to specific connection"""
        connection_id = "test-connection"
        message = {"type": "test", "data": "hello"}

        await manager.connect(mock_websocket, connection_id)
        await manager.send_personal_message(message, connection_id)

        # Check message was sent (connect also sends a welcome message)
        mock_websocket.send_json.assert_any_call(message)
        assert manager.stats["total_messages"] == 2  # 1 welcome + 1 test

    @pytest.mark.asyncio
    async def test_broadcast_to_room(self, manager):
        """Test: Broadcast message to all connections in a room"""
        room = TEST_ROOM_NAME
        message = {"type": "broadcast", "data": "test"}

        # Create TEST_ROOM_CONNECTIONS connections in the room
        websockets = []
        for i in range(TEST_ROOM_CONNECTIONS):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            connection_id = f"connection-{i}"
            await manager.connect(ws, connection_id)
            await manager.subscribe_to_room(connection_id, room)
            websockets.append(ws)

        # Broadcast
        await manager.broadcast_to_room(message, room)

        # Verify all received
        for ws in websockets:
            assert ws.send_json.call_count >= TEST_MIN_MESSAGE_COUNT  # welcome + broadcast

    @pytest.mark.asyncio
    async def test_broadcast_to_all(self, manager):
        """Test: Broadcast message to all active connections"""
        message = {"type": "global", "data": "announcement"}

        # Create TEST_BROADCAST_CONNECTIONS connections
        websockets = []
        for i in range(TEST_BROADCAST_CONNECTIONS):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            await manager.connect(ws, f"connection-{i}")
            websockets.append(ws)

        # Broadcast
        await manager.broadcast_to_all(message)

        # Verify all received
        for ws in websockets:
            assert ws.send_json.call_count >= TEST_MIN_MESSAGE_COUNT  # welcome + broadcast

    @pytest.mark.asyncio
    async def test_heartbeat_handling(self, manager, mock_websocket):
        """Test: Heartbeat ping/pong handling"""
        connection_id = "test-connection"

        await manager.connect(mock_websocket, connection_id)

        initial_time = manager.heartbeats[connection_id]
        await asyncio.sleep(TEST_SLEEP_MEDIUM)

        await manager.handle_ping(connection_id)

        # Heartbeat time should be updated
        assert manager.heartbeats[connection_id] > initial_time

    @pytest.mark.asyncio
    async def test_connection_metadata(self, manager, mock_websocket):
        """Test: Connection metadata storage and retrieval"""
        connection_id = "test-connection"
        user_id = "test-user"
        metadata = {"client": "test-client", "version": "1.0"}

        await manager.connect(
            mock_websocket,
            connection_id,
            user_id=user_id,
            metadata=metadata
        )

        info = manager.get_connection_info(connection_id)

        assert info is not None
        assert info["user_id"] == user_id
        assert info["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_error_handling_in_send(self, manager, mock_websocket):
        """Test: Error handling when sending fails"""
        connection_id = "test-connection"

        await manager.connect(mock_websocket, connection_id)

        # Make send_json raise an error
        mock_websocket.send_json.side_effect = Exception("Network error")

        # Should disconnect on error
        await manager.send_personal_message({"type": "test"}, connection_id)

        assert connection_id not in manager.active_connections

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, manager):
        """Test: Connection statistics tracking"""
        initial_stats = manager.get_stats()

        # Create connections
        for i in range(3):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            await manager.connect(ws, f"connection-{i}")

        stats = manager.get_stats()

        assert stats["total_connections"] == initial_stats["total_connections"] + 3
        assert stats["active_connections"] == 3


class TestDataPublishers:
    """Test data publishers"""

    @pytest.fixture
    def mock_service_manager(self):
        """Create mock service manager"""
        manager = Mock()

        # Mock betanet service
        betanet = Mock()
        betanet.get_status = AsyncMock(return_value={
            "active_nodes": 5,
            "connections": 10,
            "avg_latency_ms": 25.5,
            "packets_processed": 1000
        })

        # Mock scheduler service
        scheduler = Mock()
        scheduler.get_job_queue = Mock(return_value=[
            Mock(id="job1", status="pending"),
            Mock(id="job2", status="running"),
            Mock(id="job3", status="completed")
        ])

        manager.get = Mock(side_effect=lambda name: {
            "betanet": betanet,
            "scheduler": scheduler
        }.get(name))

        return manager

    @pytest.mark.asyncio
    async def test_node_status_publisher(self, mock_service_manager):
        """Test: Node status publisher collects and publishes data"""
        with patch('server.websocket.publishers.enhanced_service_manager', mock_service_manager):
            with patch('server.websocket.publishers.connection_manager') as mock_cm:
                mock_cm.broadcast_to_room = AsyncMock()

                publisher = NodeStatusPublisher()
                data = await publisher.collect_data()

                assert data is not None
                assert data["type"] == "node_status_update"
                assert data["data"]["betanet"]["active_nodes"] == 5

    @pytest.mark.asyncio
    async def test_task_progress_publisher(self, mock_service_manager):
        """Test: Task progress publisher collects task data"""
        with patch('server.websocket.publishers.enhanced_service_manager', mock_service_manager):
            publisher = TaskProgressPublisher()
            data = await publisher.collect_data()

            assert data is not None
            assert data["type"] == "task_progress_update"
            assert data["data"]["summary"]["total"] == 3

    @pytest.mark.asyncio
    async def test_publisher_start_stop(self):
        """Test: Publisher start/stop lifecycle"""
        publisher = NodeStatusPublisher()

        await publisher.start()
        assert publisher.running is True
        assert publisher._task is not None

        await publisher.stop()
        assert publisher.running is False

    @pytest.mark.asyncio
    async def test_alert_publisher_queue(self):
        """Test: Alert publisher queues and publishes alerts"""
        publisher = AlertPublisher()

        alert = {
            "type": "threshold_exceeded",
            "severity": "critical",
            "message": "CPU usage critical"
        }

        await publisher.publish_alert(alert)

        data = await publisher.collect_data()

        assert data is not None
        assert data["type"] == "alert"
        assert data["data"] == alert


class TestMetricAggregator:
    """Test metric aggregation service"""

    @pytest.fixture
    def aggregator(self):
        """Create fresh metric aggregator"""
        return MetricAggregator()

    @pytest.mark.asyncio
    async def test_record_metric(self, aggregator):
        """Test: Record metric value"""
        await aggregator.record_metric("test.metric", 100.0)

        stats = aggregator.get_metric_statistics("test.metric", "1m")

        assert stats["statistics"]["count"] == 1
        assert stats["statistics"]["avg"] == 100.0

    @pytest.mark.asyncio
    async def test_time_windows(self, aggregator):
        """Test: Metrics stored in multiple time windows"""
        await aggregator.record_metric("test.metric", 100.0)

        for window in ["1m", "5m", "1h"]:
            stats = aggregator.get_metric_statistics("test.metric", window)
            assert stats["statistics"]["count"] == 1

    @pytest.mark.asyncio
    async def test_threshold_detection(self, aggregator):
        """Test: Threshold detection triggers alerts"""
        alerts = []

        async def alert_callback(alert):
            alerts.append(alert)

        aggregator.set_alert_callback(alert_callback)

        # Record high CPU usage
        await aggregator.record_metric("cpu_usage", 95.0)

        assert len(alerts) == 1
        assert alerts[0]["type"] == "threshold_exceeded"
        assert alerts[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_anomaly_detection(self, aggregator):
        """Test: Statistical anomaly detection"""
        alerts = []

        async def alert_callback(alert):
            alerts.append(alert)

        aggregator.set_alert_callback(alert_callback)

        # Record normal values
        for i in range(20):
            await aggregator.record_metric("test.metric", 50.0 + (i % 5))

        await asyncio.sleep(TEST_SLEEP_MEDIUM)

        # Record anomalous value
        await aggregator.record_metric("test.metric", 500.0)

        # Should detect anomaly
        anomaly_alerts = [a for a in alerts if a["type"] == "anomaly_detected"]
        assert len(anomaly_alerts) > 0

    @pytest.mark.asyncio
    async def test_historical_data(self, aggregator):
        """Test: Historical data storage and retrieval"""
        # Record metrics over time
        for i in range(10):
            await aggregator.record_metric("test.metric", float(i * 10))

        history = aggregator.get_historical_data("test.metric", hours=1)

        assert len(history) >= 1

    @pytest.mark.asyncio
    async def test_statistics_calculation(self, aggregator):
        """Test: Statistical calculations (min, max, avg, stddev)"""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]

        for value in values:
            await aggregator.record_metric("test.metric", value)

        stats = aggregator.get_metric_statistics("test.metric", "1m")

        assert stats["statistics"]["min"] == 10.0
        assert stats["statistics"]["max"] == 50.0
        assert stats["statistics"]["avg"] == 30.0

    @pytest.mark.asyncio
    async def test_multiple_metrics(self, aggregator):
        """Test: Track multiple different metrics"""
        await aggregator.record_metric("cpu", 75.0)
        await aggregator.record_metric("memory", 60.0)
        await aggregator.record_metric("latency", 25.0)

        summary = aggregator.get_all_metrics_summary()

        assert "cpu" in summary["metrics"]
        assert "memory" in summary["metrics"]
        assert "latency" in summary["metrics"]


class TestTimeSeriesWindow:
    """Test time-series window management"""

    def test_add_point(self):
        """Test: Add data point to window"""
        window = TimeSeriesWindow(window_seconds=TEST_WINDOW_SECONDS)
        window.add_point(100.0)

        assert len(window.data_points) == 1

    def test_max_points_limit(self):
        """Test: Respect max points limit"""
        window = TimeSeriesWindow(window_seconds=TEST_WINDOW_SECONDS, max_points=TEST_MAX_WINDOW_POINTS)

        for i in range(20):
            window.add_point(float(i))

        assert len(window.data_points) == TEST_MAX_WINDOW_POINTS

    def test_statistics_calculation(self):
        """Test: Calculate statistics for window"""
        window = TimeSeriesWindow(window_seconds=TEST_WINDOW_SECONDS)

        for value in [10.0, 20.0, 30.0, 40.0, 50.0]:
            window.add_point(value)

        stats = window.get_statistics()

        assert stats["count"] == 5
        assert stats["min"] == 10.0
        assert stats["max"] == 50.0
        assert stats["avg"] == 30.0


class TestAnomalyDetector:
    """Test anomaly detection"""

    def test_detect_anomaly(self):
        """Test: Detect statistical outliers"""
        detector = AnomalyDetector(threshold_stddev=2.0)

        stats = {
            "count": 100,
            "avg": 50.0,
            "stddev": 5.0
        }

        # Normal value
        assert detector.detect_anomaly(52.0, stats) is None

        # Anomalous value
        anomaly = detector.detect_anomaly(100.0, stats)
        assert anomaly is not None
        assert anomaly["severity"] in ["medium", "high"]

    def test_insufficient_data(self):
        """Test: No detection with insufficient data"""
        detector = AnomalyDetector()

        stats = {
            "count": 5,  # Too few data points
            "avg": 50.0,
            "stddev": 5.0
        }

        assert detector.detect_anomaly(100.0, stats) is None


class TestPublisherManager:
    """Test publisher manager orchestration"""

    @pytest.mark.asyncio
    async def test_start_all_publishers(self):
        """Test: Start all publishers"""
        manager = PublisherManager()

        await manager.start_all()

        assert len(manager.publishers) == TEST_PUBLISHER_COUNT  # 6 publisher types
        assert all(p.running for p in manager.publishers)

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_stop_all_publishers(self):
        """Test: Stop all publishers"""
        manager = PublisherManager()

        await manager.start_all()
        await manager.stop_all()

        assert len(manager.publishers) == 0

    @pytest.mark.asyncio
    async def test_manual_alert_publishing(self):
        """Test: Manually publish alerts"""
        manager = PublisherManager()

        await manager.start_all()

        alert = {"type": "test", "message": "Test alert"}
        await manager.publish_alert(alert)

        await manager.stop_all()


# Integration Tests
class TestWebSocketIntegration:
    """Integration tests for complete WebSocket system"""

    @pytest.mark.asyncio
    async def test_end_to_end_message_flow(self):
        """Test: End-to-end message flow from publisher to client"""
        manager = ConnectionManager()
        await manager.start()

        # Create mock websocket
        ws = AsyncMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        # Connect and subscribe
        connection_id = "test-connection"
        await manager.connect(ws, connection_id)
        await manager.subscribe_to_room(connection_id, TEST_ROOM_NAME)

        # Broadcast message
        message = {"type": "test", "data": "integration-test"}
        await manager.broadcast_to_room(message, TEST_ROOM_NAME)

        # Verify message received
        assert ws.send_json.call_count >= TEST_MIN_MESSAGE_COUNT  # welcome + test message

        await manager.stop()

    @pytest.mark.asyncio
    async def test_load_handling(self):
        """Test: Handle high load (TEST_CONNECTIONS_LARGE concurrent connections)"""
        manager = ConnectionManager()
        await manager.start()

        connections = []

        # Create TEST_CONNECTIONS_LARGE connections
        for i in range(TEST_CONNECTIONS_LARGE):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            connection_id = f"load-test-{i}"
            await manager.connect(ws, connection_id)
            connections.append((connection_id, ws))

        assert len(manager.active_connections) == TEST_CONNECTIONS_LARGE

        # Broadcast to all
        await manager.broadcast_to_all({"type": "load_test"})

        # Cleanup
        for connection_id, ws in connections:
            await manager.disconnect(connection_id)

        await manager.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
