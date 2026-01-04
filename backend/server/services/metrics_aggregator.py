"""
Metric Aggregation Service
Collects and aggregates metrics with time-series data and anomaly detection
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import deque, defaultdict
import statistics
import json

from backend.server.constants import (
    METRICS_BATCH_SIZE,
    METRICS_FLUSH_INTERVAL,
    ONE_MINUTE,
)

logger = logging.getLogger(__name__)


class TimeSeriesWindow:
    """Manages time-series data for a specific window"""

    def __init__(self, window_seconds: int, max_points: int = METRICS_BATCH_SIZE):
        self.window_seconds = window_seconds
        self.max_points = max_points
        self.data_points = deque(maxlen=max_points)

    def add_point(self, value: float, timestamp: Optional[datetime] = None):
        """Add a data point"""
        if timestamp is None:
            timestamp = datetime.now()

        self.data_points.append({
            "value": value,
            "timestamp": timestamp
        })

    def get_points_in_window(self) -> List[Dict[str, Any]]:
        """Get all points within the time window"""
        cutoff = datetime.now() - timedelta(seconds=self.window_seconds)
        return [
            p for p in self.data_points
            if p["timestamp"] >= cutoff
        ]

    def get_statistics(self) -> Dict[str, float]:
        """Calculate statistics for points in window"""
        points = self.get_points_in_window()

        if not points:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "avg": 0,
                "median": 0,
                "stddev": 0
            }

        values = [p["value"] for p in points]

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": statistics.mean(values),
            "median": statistics.median(values),
            "stddev": statistics.stdev(values) if len(values) > 1 else 0
        }


class AnomalyDetector:
    """Detects anomalies using statistical methods"""

    def __init__(self, threshold_stddev: float = 2.5):
        self.threshold_stddev = threshold_stddev

    def detect_anomaly(self, value: float, stats: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """
        Detect if a value is anomalous using statistical outlier detection

        Returns anomaly info if detected, None otherwise
        """
        if stats["count"] < 10:
            # Not enough data for reliable detection
            return None

        avg = stats["avg"]
        stddev = stats["stddev"]

        if stddev == 0:
            # No variance
            return None

        z_score = abs((value - avg) / stddev)

        if z_score > self.threshold_stddev:
            return {
                "value": value,
                "expected": avg,
                "z_score": z_score,
                "severity": "high" if z_score > 3.5 else "medium",
                "timestamp": datetime.now().isoformat()
            }

        return None


class MetricAggregator:
    """
    Aggregates metrics from all services with time-series support
    """

    def __init__(self):
        # Time windows: 1 minute, 5 minutes, 1 hour
        self.windows = {
            "1m": ONE_MINUTE,
            "5m": 5 * ONE_MINUTE,
            "1h": 60 * ONE_MINUTE
        }

        # Metric storage: {metric_name: {window: TimeSeriesWindow}}
        self.metrics: Dict[str, Dict[str, TimeSeriesWindow]] = defaultdict(lambda: {
            window: TimeSeriesWindow(seconds)
            for window, seconds in self.windows.items()
        })

        # Alert thresholds
        self.thresholds = {
            "cpu_usage": {"warning": 70.0, "critical": 90.0},
            "memory_usage": {"warning": 80.0, "critical": 95.0},
            "latency_ms": {"warning": 100.0, "critical": 500.0},
            "error_rate": {"warning": 5.0, "critical": 10.0}
        }

        # Anomaly detector
        self.anomaly_detector = AnomalyDetector(threshold_stddev=2.5)

        # Alert callback
        self.alert_callback = None

        # Historical data (last 7 days)
        self.retention_days = 7
        self.historical_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def set_alert_callback(self, callback):
        """Set callback function for alerts"""
        self.alert_callback = callback

    async def record_metric(
        self,
        metric_name: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record a metric value

        Args:
            metric_name: Name of the metric
            value: Metric value
            metadata: Optional metadata
        """
        timestamp = datetime.now()

        # Add to all time windows
        for window_name, window in self.metrics[metric_name].items():
            window.add_point(value, timestamp)

        # Add to historical data with compression
        if len(self.historical_data[metric_name]) == 0 or \
           (timestamp - datetime.fromisoformat(self.historical_data[metric_name][-1]["timestamp"])).seconds >= METRICS_FLUSH_INTERVAL:
            self.historical_data[metric_name].append({
                "value": value,
                "timestamp": timestamp.isoformat(),
                "metadata": metadata
            })

        # Check for anomalies
        stats = self.metrics[metric_name]["5m"].get_statistics()
        anomaly = self.anomaly_detector.detect_anomaly(value, stats)

        if anomaly and self.alert_callback:
            await self.alert_callback({
                "type": "anomaly_detected",
                "metric": metric_name,
                "anomaly": anomaly,
                "metadata": metadata
            })

        # Check thresholds
        if metric_name in self.thresholds:
            await self._check_threshold(metric_name, value, metadata)

    async def _check_threshold(
        self,
        metric_name: str,
        value: float,
        metadata: Optional[Dict[str, Any]]
    ):
        """Check if metric exceeds thresholds"""
        thresholds = self.thresholds[metric_name]

        if value >= thresholds["critical"]:
            severity = "critical"
        elif value >= thresholds["warning"]:
            severity = "warning"
        else:
            return

        if self.alert_callback:
            await self.alert_callback({
                "type": "threshold_exceeded",
                "metric": metric_name,
                "value": value,
                "threshold": thresholds[severity],
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata
            })

    def get_metric_statistics(
        self,
        metric_name: str,
        window: str = "5m"
    ) -> Dict[str, Any]:
        """
        Get statistics for a metric in a specific time window

        Args:
            metric_name: Name of the metric
            window: Time window (1m, 5m, 1h)

        Returns:
            Statistics dictionary
        """
        if metric_name not in self.metrics:
            return {"error": "Metric not found"}

        if window not in self.metrics[metric_name]:
            return {"error": "Invalid window"}

        stats = self.metrics[metric_name][window].get_statistics()

        return {
            "metric": metric_name,
            "window": window,
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }

    def get_historical_data(
        self,
        metric_name: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get historical data for a metric

        Args:
            metric_name: Name of the metric
            hours: Number of hours of history

        Returns:
            List of historical data points
        """
        if metric_name not in self.historical_data:
            return []

        cutoff = datetime.now() - timedelta(hours=hours)

        return [
            point for point in self.historical_data[metric_name]
            if datetime.fromisoformat(point["timestamp"]) >= cutoff
        ]

    def compress_data(self):
        """Compress historical data older than retention period"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        for metric_name in self.historical_data:
            self.historical_data[metric_name] = [
                point for point in self.historical_data[metric_name]
                if datetime.fromisoformat(point["timestamp"]) >= cutoff
            ]

    def get_all_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
        summary = {}

        for metric_name in self.metrics:
            summary[metric_name] = {
                window: self.metrics[metric_name][window].get_statistics()
                for window in self.windows
            }

        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": summary,
            "historical_count": {
                metric: len(points)
                for metric, points in self.historical_data.items()
            }
        }

    async def aggregate_from_services(self, service_manager):
        """
        Aggregate metrics from all services

        Args:
            service_manager: Service manager instance
        """
        try:
            # Betanet metrics
            betanet = service_manager.get('betanet')
            if betanet:
                status = await betanet.get_status()
                await self.record_metric("betanet.active_nodes", status.get('active_nodes', 0))
                await self.record_metric("betanet.latency_ms", status.get('avg_latency_ms', 0))
                await self.record_metric("betanet.connections", status.get('connections', 0))

            # P2P metrics
            p2p = service_manager.get('p2p')
            if p2p and hasattr(p2p, 'get_health'):
                health = p2p.get_health()
                await self.record_metric("p2p.connected_peers", health.get('connected_peers', 0))

            # Scheduler metrics
            scheduler = service_manager.get('scheduler')
            if scheduler and hasattr(scheduler, 'get_job_queue'):
                jobs = scheduler.get_job_queue()
                await self.record_metric("scheduler.total_jobs", len(jobs))
                await self.record_metric("scheduler.running_jobs",
                                        len([j for j in jobs if getattr(j, 'status', None) == 'running']))

            # Edge metrics
            edge = service_manager.get('edge')
            if edge and hasattr(edge, 'get_registered_devices'):
                devices = edge.get_registered_devices()
                await self.record_metric("edge.total_devices", len(devices))

                if devices:
                    avg_cpu = sum(getattr(d, 'cpu_usage', 0) for d in devices) / len(devices)
                    avg_memory = sum(getattr(d, 'memory_usage', 0) for d in devices) / len(devices)
                    await self.record_metric("edge.avg_cpu_usage", avg_cpu)
                    await self.record_metric("edge.avg_memory_usage", avg_memory)

        except Exception as e:
            logger.error(f"Error aggregating metrics: {e}")


# Global metrics aggregator instance
metrics_aggregator = MetricAggregator()
