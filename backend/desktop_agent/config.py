"""
Desktop Agent Configuration
Cross-platform configuration management

PHASE3-AGENT-001: Cross-Platform Compatibility
- Uses pathlib for paths
- Platform-specific default locations
"""
import json
import logging
import os
import platform
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


def get_platform() -> str:
    """Get normalized platform name."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system


def get_config_dir() -> Path:
    """
    Get platform-specific config directory.

    PHASE3-AGENT-001: Cross-platform paths.
    """
    system = get_platform()

    if system == "windows":
        # %APPDATA%/fogburst
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "macos":
        # ~/Library/Application Support/fogburst
        base = Path.home() / "Library" / "Application Support"
    else:
        # ~/.config/fogburst (Linux/other)
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    return base / "fogburst"


def get_data_dir() -> Path:
    """
    Get platform-specific data directory.

    PHASE3-AGENT-001: Cross-platform paths.
    """
    system = get_platform()

    if system == "windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "macos":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    return base / "fogburst"


def get_cache_dir() -> Path:
    """
    Get platform-specific cache directory.

    PHASE3-AGENT-001: Cross-platform paths.
    """
    system = get_platform()

    if system == "windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "fogburst" / "cache"
    elif system == "macos":
        return Path.home() / "Library" / "Caches" / "fogburst"
    else:
        return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "fogburst"


def get_log_dir() -> Path:
    """
    Get platform-specific log directory.

    PHASE3-AGENT-001: Cross-platform paths.
    """
    system = get_platform()

    if system == "windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "fogburst" / "logs"
    elif system == "macos":
        return Path.home() / "Library" / "Logs" / "fogburst"
    else:
        return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "fogburst" / "logs"


@dataclass
class AgentConfig:
    """
    Desktop agent configuration.

    PHASE3-AGENT-001: Cross-platform config structure.
    """
    # Device identity
    device_id: str = ""
    device_name: str = ""

    # Coordinator connection
    coordinator_url: Optional[str] = None  # Manual override
    coordinator_port: int = 8000

    # Discovery (PHASE3-AGENT-003)
    enable_mdns_discovery: bool = True
    discovery_timeout_sec: int = 30
    discovery_service_name: str = "_fogburst._tcp.local."

    # Authentication
    enrollment_code: Optional[str] = None
    auth_token: Optional[str] = None

    # Task capabilities
    task_types: list[str] = field(default_factory=lambda: ["compute"])
    max_concurrent_tasks: int = 2

    # Resource limits (PHASE3-AGENT-004)
    max_cpu_percent: float = 80.0
    max_memory_percent: float = 70.0
    pause_on_overload: bool = True

    # Heartbeat
    heartbeat_interval_sec: int = 30
    heartbeat_timeout_sec: int = 10

    # Retry (PHASE3-AGENT-003)
    max_retries: int = 5
    retry_base_delay_sec: float = 1.0
    retry_max_delay_sec: float = 60.0

    # TLS
    tls_enabled: bool = True
    tls_verify: bool = True
    tls_cert_path: Optional[str] = None

    # Directories
    config_dir: str = ""
    data_dir: str = ""
    cache_dir: str = ""
    log_dir: str = ""

    def __post_init__(self):
        """Set default directories after init."""
        if not self.config_dir:
            self.config_dir = str(get_config_dir())
        if not self.data_dir:
            self.data_dir = str(get_data_dir())
        if not self.cache_dir:
            self.cache_dir = str(get_cache_dir())
        if not self.log_dir:
            self.log_dir = str(get_log_dir())

        if not self.device_id:
            self.device_id = self._generate_device_id()

        if not self.device_name:
            self.device_name = platform.node() or f"device-{self.device_id[:8]}"

    def _generate_device_id(self) -> str:
        """Generate unique device ID."""
        import hashlib
        import uuid

        # Combine machine-specific info
        machine_info = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
        return hashlib.sha256(machine_info.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: Optional[Path] = None) -> Path:
        """
        Save configuration to file.

        Args:
            path: Optional path (defaults to config_dir/config.json)

        Returns:
            Path to saved file
        """
        if path is None:
            config_dir = Path(self.config_dir)
            config_dir.mkdir(parents=True, exist_ok=True)
            path = config_dir / "config.json"

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"Configuration saved to {path}")
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AgentConfig":
        """
        Load configuration from file.

        Args:
            path: Optional path (defaults to config_dir/config.json)

        Returns:
            Loaded configuration
        """
        if path is None:
            path = get_config_dir() / "config.json"

        if not path.exists():
            logger.info(f"No config file at {path}, using defaults")
            return cls()

        with open(path) as f:
            data = json.load(f)

        logger.info(f"Configuration loaded from {path}")
        return cls.from_dict(data)


def ensure_directories(config: AgentConfig) -> None:
    """
    Ensure all agent directories exist.

    PHASE3-AGENT-001: Cross-platform directory setup.
    """
    for dir_path in [config.config_dir, config.data_dir, config.cache_dir, config.log_dir]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory: {dir_path}")
