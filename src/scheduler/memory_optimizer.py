"""
Memory Optimizer - Advanced memory management and optimization

Features:
- Memory arena allocation (pre-allocate 1GB buffer)
- Zero-copy operations where possible
- Lazy loading for large objects
- Garbage collection tuning
- Memory pressure monitoring
- Memory leak detection
"""

import gc
import logging
import mmap
import os
import sys
import threading
import tracemalloc
import weakref
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
from enum import Enum

import psutil

logger = logging.getLogger(__name__)

T = TypeVar('T')


class MemoryPressureLevel(Enum):
    """Memory pressure levels"""
    LOW = "low"  # < 70%
    MEDIUM = "medium"  # 70-85%
    HIGH = "high"  # 85-95%
    CRITICAL = "critical"  # > 95%


@dataclass
class MemoryStats:
    """Memory usage statistics"""
    total_bytes: int
    available_bytes: int
    used_bytes: int
    percent_used: float
    pressure_level: MemoryPressureLevel
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def current(cls) -> 'MemoryStats':
        """Get current memory statistics"""
        mem = psutil.virtual_memory()

        if mem.percent < 70:
            pressure = MemoryPressureLevel.LOW
        elif mem.percent < 85:
            pressure = MemoryPressureLevel.MEDIUM
        elif mem.percent < 95:
            pressure = MemoryPressureLevel.HIGH
        else:
            pressure = MemoryPressureLevel.CRITICAL

        return cls(
            total_bytes=mem.total,
            available_bytes=mem.available,
            used_bytes=mem.used,
            percent_used=mem.percent,
            pressure_level=pressure,
        )


class MemoryArena:
    """
    Pre-allocated memory arena for fast allocation/deallocation

    Uses memory-mapped file for efficient buffer management
    """

    def __init__(self, size_bytes: int = 1024 * 1024 * 1024):  # 1GB default
        self.size_bytes = size_bytes
        self._mmap: Optional[mmap.mmap] = None
        self._offset = 0
        self._lock = threading.Lock()
        self._allocations: Dict[int, int] = {}  # offset -> size
        self._free_blocks: List[tuple[int, int]] = []  # (offset, size)

        self._initialize_arena()
        logger.info(f"MemoryArena initialized with {size_bytes / (1024**3):.2f} GB")

    def _initialize_arena(self) -> None:
        """Initialize the memory-mapped arena"""
        try:
            # Create anonymous memory mapping
            self._mmap = mmap.mmap(-1, self.size_bytes)
            self._free_blocks = [(0, self.size_bytes)]
        except Exception as e:
            logger.error(f"Failed to initialize memory arena: {e}")
            raise

    def allocate(self, size: int) -> Optional[memoryview]:
        """Allocate a block of memory from the arena"""
        with self._lock:
            # Find best-fit free block
            best_idx = -1
            best_size = float('inf')

            for idx, (offset, block_size) in enumerate(self._free_blocks):
                if block_size >= size and block_size < best_size:
                    best_idx = idx
                    best_size = block_size

            if best_idx == -1:
                logger.warning(f"Failed to allocate {size} bytes from arena")
                return None

            # Allocate from this block
            offset, block_size = self._free_blocks.pop(best_idx)
            self._allocations[offset] = size

            # If block is larger, add remainder back to free list
            if block_size > size:
                self._free_blocks.append((offset + size, block_size - size))

            # Return memory view
            return memoryview(self._mmap)[offset:offset + size]

    def deallocate(self, view: memoryview) -> None:
        """Deallocate a memory block back to the arena"""
        with self._lock:
            # Find the allocation
            offset = None
            for alloc_offset, size in self._allocations.items():
                # Check if this view matches an allocation
                if view.nbytes == size:
                    offset = alloc_offset
                    break

            if offset is None:
                logger.warning("Attempted to deallocate unknown memory block")
                return

            size = self._allocations.pop(offset)
            self._free_blocks.append((offset, size))

            # Merge adjacent free blocks
            self._merge_free_blocks()

            # Release the memoryview to prevent BufferError on shutdown
            try:
                view.release()
            except Exception:
                pass  # View may already be released

    def _merge_free_blocks(self) -> None:
        """Merge adjacent free blocks"""
        if len(self._free_blocks) < 2:
            return

        # Sort by offset
        self._free_blocks.sort()

        merged = []
        current_offset, current_size = self._free_blocks[0]

        for offset, size in self._free_blocks[1:]:
            # If adjacent, merge
            if current_offset + current_size == offset:
                current_size += size
            else:
                merged.append((current_offset, current_size))
                current_offset, current_size = offset, size

        merged.append((current_offset, current_size))
        self._free_blocks = merged

    def get_stats(self) -> Dict[str, Any]:
        """Get arena statistics"""
        with self._lock:
            total_allocated = sum(self._allocations.values())
            total_free = sum(size for _, size in self._free_blocks)

            return {
                "total_bytes": self.size_bytes,
                "allocated_bytes": total_allocated,
                "free_bytes": total_free,
                "allocation_count": len(self._allocations),
                "free_blocks": len(self._free_blocks),
                "utilization_percent": round(total_allocated / self.size_bytes * 100, 2),
            }

    def reset(self) -> None:
        """Reset the arena, clearing all allocations"""
        with self._lock:
            self._allocations.clear()
            self._free_blocks = [(0, self.size_bytes)]
            logger.info("MemoryArena reset")

    def shutdown(self) -> None:
        """Shutdown the arena"""
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        logger.info("MemoryArena shut down")


class LazyLoader(Generic[T]):
    """
    Lazy loader for large objects

    Only loads the object when first accessed
    """

    def __init__(self, loader: Callable[[], T]):
        self._loader = loader
        self._value: Optional[T] = None
        self._loaded = False
        self._lock = threading.Lock()

    @property
    def value(self) -> T:
        """Get the value, loading if necessary"""
        if not self._loaded:
            with self._lock:
                if not self._loaded:  # Double-check locking
                    self._value = self._loader()
                    self._loaded = True
                    logger.debug(f"Lazy loaded object of type {type(self._value).__name__}")

        return self._value

    def is_loaded(self) -> bool:
        """Check if the value has been loaded"""
        return self._loaded

    def unload(self) -> None:
        """Unload the value to free memory"""
        with self._lock:
            if self._loaded:
                self._value = None
                self._loaded = False
                logger.debug("Unloaded lazy object")


class MemoryLeakDetector:
    """Detect memory leaks by tracking object creation"""

    def __init__(self):
        self._tracking = False
        self._snapshots: List[tracemalloc.Snapshot] = []
        self._reference_counts: Dict[type, List[int]] = defaultdict(list)
        logger.info("MemoryLeakDetector initialized")

    def start_tracking(self) -> None:
        """Start tracking memory allocations"""
        if not self._tracking:
            tracemalloc.start()
            self._tracking = True
            self._take_snapshot()
            logger.info("Started memory leak tracking")

    def stop_tracking(self) -> None:
        """Stop tracking memory allocations"""
        if self._tracking:
            tracemalloc.stop()
            self._tracking = False
            logger.info("Stopped memory leak tracking")

    def _take_snapshot(self) -> None:
        """Take a memory snapshot"""
        if self._tracking:
            snapshot = tracemalloc.take_snapshot()
            self._snapshots.append(snapshot)

            # Track reference counts for common types
            for obj_type in [list, dict, set, str]:
                count = sum(1 for obj in gc.get_objects() if type(obj) is obj_type)
                self._reference_counts[obj_type].append(count)

    def check_for_leaks(self) -> Dict[str, Any]:
        """Check for potential memory leaks"""
        if not self._tracking or len(self._snapshots) < 2:
            return {"error": "Not enough snapshots to analyze"}

        self._take_snapshot()

        # Compare last two snapshots
        stats = self._snapshots[-1].compare_to(self._snapshots[-2], 'lineno')

        # Find top memory increases
        top_increases = []
        for stat in stats[:10]:
            top_increases.append({
                "file": stat.traceback.format()[0] if stat.traceback else "unknown",
                "size_diff_kb": stat.size_diff / 1024,
                "count_diff": stat.count_diff,
            })

        # Check for growing object counts
        growing_types = []
        for obj_type, counts in self._reference_counts.items():
            if len(counts) >= 3:
                # Check if consistently growing
                if counts[-1] > counts[-2] > counts[-3]:
                    growing_types.append({
                        "type": obj_type.__name__,
                        "count": counts[-1],
                        "growth": counts[-1] - counts[-3],
                    })

        return {
            "top_memory_increases": top_increases,
            "growing_object_types": growing_types,
            "total_snapshots": len(self._snapshots),
        }


class MemoryOptimizer:
    """
    Centralized memory optimization manager

    Coordinates arena allocation, lazy loading, GC tuning, and leak detection
    """

    def __init__(self, arena_size_gb: float = 1.0):
        self.arena = MemoryArena(int(arena_size_gb * 1024 * 1024 * 1024))
        self.leak_detector = MemoryLeakDetector()
        self._pressure_callbacks: List[Callable[[MemoryPressureLevel], None]] = []
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

        # Tune garbage collection for performance
        self._tune_gc()

        logger.info("MemoryOptimizer initialized")

    def _tune_gc(self) -> None:
        """Tune garbage collector for better performance"""
        # Increase thresholds to reduce GC frequency
        gc.set_threshold(1000, 15, 15)  # Default is (700, 10, 10)

        # Enable automatic garbage collection
        gc.enable()

        logger.info("Garbage collection tuned for performance")

    def register_pressure_callback(
        self, callback: Callable[[MemoryPressureLevel], None]
    ) -> None:
        """Register a callback for memory pressure events"""
        self._pressure_callbacks.append(callback)

    def start_monitoring(self, interval: float = 5.0) -> None:
        """Start monitoring memory pressure"""
        if self._monitoring:
            return

        self._monitoring = True

        def monitor_loop():
            last_pressure = MemoryPressureLevel.LOW

            while self._monitoring:
                stats = MemoryStats.current()

                # If pressure level changed, notify callbacks
                if stats.pressure_level != last_pressure:
                    logger.warning(
                        f"Memory pressure changed: {last_pressure.value} -> {stats.pressure_level.value} "
                        f"({stats.percent_used:.1f}% used)"
                    )

                    for callback in self._pressure_callbacks:
                        try:
                            callback(stats.pressure_level)
                        except Exception as e:
                            logger.error(f"Error in pressure callback: {e}")

                    last_pressure = stats.pressure_level

                threading.Event().wait(interval)

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval={interval}s)")

    def stop_monitoring(self) -> None:
        """Stop monitoring memory pressure"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None
        logger.info("Stopped memory monitoring")

    def force_gc(self) -> Dict[str, int]:
        """Force garbage collection and return stats"""
        collected = {
            "gen0": gc.collect(0),
            "gen1": gc.collect(1),
            "gen2": gc.collect(2),
        }

        logger.info(f"Forced GC collected: {collected}")
        return collected

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics"""
        process = psutil.Process()
        process_mem = process.memory_info()

        return {
            "system": MemoryStats.current().__dict__,
            "process": {
                "rss_mb": process_mem.rss / (1024 * 1024),
                "vms_mb": process_mem.vms / (1024 * 1024),
                "percent": process.memory_percent(),
            },
            "arena": self.arena.get_stats(),
            "gc": {
                "counts": gc.get_count(),
                "thresholds": gc.get_threshold(),
                "objects": len(gc.get_objects()),
            },
        }

    def create_lazy_loader(self, loader: Callable[[], T]) -> LazyLoader[T]:
        """Create a lazy loader for an object"""
        return LazyLoader(loader)

    def shutdown(self) -> None:
        """Shutdown the memory optimizer"""
        self.stop_monitoring()
        self.leak_detector.stop_tracking()
        self.arena.shutdown()
        logger.info("MemoryOptimizer shut down")


# Singleton instance
_optimizer = MemoryOptimizer()


def get_memory_optimizer() -> MemoryOptimizer:
    """Get the singleton MemoryOptimizer instance"""
    return _optimizer
