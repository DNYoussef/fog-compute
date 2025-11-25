"""
Centralized Configuration Module for Fog-Compute Project

This module provides a unified configuration system for all fog-compute components.
All hardcoded network addresses, ports, and magic numbers should be sourced from this module.

Usage:
    from config import config

    # Access network settings
    betanet_host = config.network.betanet_host
    redis_port = config.redis.port

    # Access tokenomics settings
    reward_rate = config.tokenomics.reward_rate_per_hour

    # Access privacy settings
    circuit_hops = config.privacy.min_circuit_hops

Environment Variables:
    FOG_BETANET_HOST: BetaNet server host (default: 127.0.0.1)
    FOG_BETANET_PORT: BetaNet server port (default: 9000)
    FOG_BETANET_API_PORT: BetaNet API port (default: 8443)
    FOG_REDIS_HOST: Redis server host (default: localhost)
    FOG_REDIS_PORT: Redis server port (default: 6379)
    FOG_API_HOST: API gateway host (default: localhost)
    FOG_API_PORT: API gateway port (default: 8080)
    FOG_BITCHAT_HOST: BitChat server host (default: localhost)
    FOG_BITCHAT_PORT: BitChat server port (default: 8000)
    FOG_COORDINATOR_PORT: Fog coordinator port (default: 8080)
    FOG_REWARD_RATE: Token reward rate per hour (default: 10.0)
    FOG_MIN_CIRCUIT_HOPS: Minimum circuit hops for privacy (default: 3)
    FOG_MAX_CIRCUITS: Maximum concurrent circuits (default: 50)
    FOG_CIRCUIT_LIFETIME: Circuit lifetime in minutes (default: 30)
"""

from dataclasses import dataclass, field
import os
from typing import Optional


def get_env_int(key: str, default: int) -> int:
    """Get integer value from environment variable with fallback to default."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_float(key: str, default: float) -> float:
    """Get float value from environment variable with fallback to default."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def get_env_bool(key: str, default: bool) -> bool:
    """Get boolean value from environment variable with fallback to default."""
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ('true', '1', 'yes', 'on')


@dataclass
class NetworkConfig:
    """Network configuration for all fog-compute services.

    Attributes:
        betanet_host: BetaNet server host address
        betanet_port: BetaNet server main port (transport layer)
        betanet_api_port: BetaNet HTTP API port
        redis_host: Redis server host address
        redis_port: Redis server port
        api_host: API gateway host address
        api_port: API gateway port
        bitchat_host: BitChat server host address
        bitchat_port: BitChat server port
        coordinator_port: Fog coordinator service port
        connection_timeout: Default connection timeout in seconds
        request_timeout: Default request timeout in seconds
        max_retries: Maximum number of connection retries
    """
    betanet_host: str = field(default_factory=lambda: os.getenv('FOG_BETANET_HOST', '127.0.0.1'))
    betanet_port: int = field(default_factory=lambda: get_env_int('FOG_BETANET_PORT', 9000))
    betanet_api_port: int = field(default_factory=lambda: get_env_int('FOG_BETANET_API_PORT', 8443))

    redis_host: str = field(default_factory=lambda: os.getenv('FOG_REDIS_HOST', 'localhost'))
    redis_port: int = field(default_factory=lambda: get_env_int('FOG_REDIS_PORT', 6379))

    api_host: str = field(default_factory=lambda: os.getenv('FOG_API_HOST', 'localhost'))
    api_port: int = field(default_factory=lambda: get_env_int('FOG_API_PORT', 8080))

    bitchat_host: str = field(default_factory=lambda: os.getenv('FOG_BITCHAT_HOST', 'localhost'))
    bitchat_port: int = field(default_factory=lambda: get_env_int('FOG_BITCHAT_PORT', 8000))

    coordinator_port: int = field(default_factory=lambda: get_env_int('FOG_COORDINATOR_PORT', 8080))

    connection_timeout: int = field(default_factory=lambda: get_env_int('FOG_CONNECTION_TIMEOUT', 30))
    request_timeout: int = field(default_factory=lambda: get_env_int('FOG_REQUEST_TIMEOUT', 60))
    max_retries: int = field(default_factory=lambda: get_env_int('FOG_MAX_RETRIES', 3))

    @property
    def redis_url(self) -> str:
        """Generate Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def betanet_api_url(self) -> str:
        """Generate BetaNet API URL."""
        return f"http://{self.betanet_host}:{self.betanet_api_port}"

    @property
    def bitchat_api_url(self) -> str:
        """Generate BitChat API URL."""
        return f"http://{self.bitchat_host}:{self.bitchat_port}"

    @property
    def api_gateway_url(self) -> str:
        """Generate API gateway URL."""
        return f"http://{self.api_host}:{self.api_port}"


@dataclass
class BetanetConfig:
    """BetaNet-specific configuration settings.

    Attributes:
        server_host: BetaNet server host for incoming connections
        server_port: BetaNet server port for transport layer
        api_port: HTTP API port for BetaNet services
        max_peers: Maximum number of concurrent peer connections
        peer_discovery_interval: Peer discovery interval in seconds
        heartbeat_interval: Peer heartbeat interval in seconds
        relay_enabled: Enable relay node functionality
        relay_lottery_enabled: Enable relay lottery mechanism
    """
    server_host: str = field(default_factory=lambda: os.getenv('FOG_BETANET_SERVER_HOST', '127.0.0.1'))
    server_port: int = field(default_factory=lambda: get_env_int('FOG_BETANET_SERVER_PORT', 9000))
    api_port: int = field(default_factory=lambda: get_env_int('FOG_BETANET_API_PORT', 8443))

    max_peers: int = field(default_factory=lambda: get_env_int('FOG_BETANET_MAX_PEERS', 100))
    peer_discovery_interval: int = field(default_factory=lambda: get_env_int('FOG_BETANET_DISCOVERY_INTERVAL', 60))
    heartbeat_interval: int = field(default_factory=lambda: get_env_int('FOG_BETANET_HEARTBEAT_INTERVAL', 30))

    relay_enabled: bool = field(default_factory=lambda: get_env_bool('FOG_BETANET_RELAY_ENABLED', True))
    relay_lottery_enabled: bool = field(default_factory=lambda: get_env_bool('FOG_BETANET_RELAY_LOTTERY', True))


@dataclass
class RedisConfig:
    """Redis configuration settings.

    Attributes:
        host: Redis server host address
        port: Redis server port
        db: Redis database number
        password: Redis authentication password (optional)
        max_connections: Maximum connection pool size
        socket_timeout: Socket operation timeout in seconds
        socket_connect_timeout: Socket connection timeout in seconds
        decode_responses: Decode byte responses to strings
    """
    host: str = field(default_factory=lambda: os.getenv('FOG_REDIS_HOST', 'localhost'))
    port: int = field(default_factory=lambda: get_env_int('FOG_REDIS_PORT', 6379))
    db: int = field(default_factory=lambda: get_env_int('FOG_REDIS_DB', 0))
    password: Optional[str] = field(default_factory=lambda: os.getenv('FOG_REDIS_PASSWORD'))

    max_connections: int = field(default_factory=lambda: get_env_int('FOG_REDIS_MAX_CONNECTIONS', 50))
    socket_timeout: int = field(default_factory=lambda: get_env_int('FOG_REDIS_SOCKET_TIMEOUT', 5))
    socket_connect_timeout: int = field(default_factory=lambda: get_env_int('FOG_REDIS_CONNECT_TIMEOUT', 5))
    decode_responses: bool = field(default_factory=lambda: get_env_bool('FOG_REDIS_DECODE_RESPONSES', True))

    @property
    def connection_url(self) -> str:
        """Generate Redis connection URL with optional password."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class TokenomicsConfig:
    """Tokenomics and reward system configuration.

    Attributes:
        reward_rate_per_hour: Base token reward rate per hour
        staking_reward_multiplier: Multiplier for staked tokens
        performance_bonus_threshold: Performance score threshold for bonus
        performance_bonus_rate: Bonus rate for high performers
        transfer_fee_percentage: Fee percentage for token transfers
        max_transfer_amount: Maximum single transfer amount
        failure_rate_threshold: Acceptable failure rate threshold
        min_balance_warning: Minimum balance for warning threshold
    """
    reward_rate_per_hour: float = field(default_factory=lambda: get_env_float('FOG_REWARD_RATE', 10.0))
    staking_reward_multiplier: float = field(default_factory=lambda: get_env_float('FOG_STAKING_MULTIPLIER', 1.5))

    performance_bonus_threshold: float = field(default_factory=lambda: get_env_float('FOG_PERFORMANCE_THRESHOLD', 0.95))
    performance_bonus_rate: float = field(default_factory=lambda: get_env_float('FOG_PERFORMANCE_BONUS', 0.2))

    transfer_fee_percentage: float = field(default_factory=lambda: get_env_float('FOG_TRANSFER_FEE', 0.01))
    max_transfer_amount: float = field(default_factory=lambda: get_env_float('FOG_MAX_TRANSFER', 10000.0))

    failure_rate_threshold: float = field(default_factory=lambda: get_env_float('FOG_FAILURE_THRESHOLD', 0.05))
    min_balance_warning: float = field(default_factory=lambda: get_env_float('FOG_MIN_BALANCE', 100.0))


@dataclass
class PrivacyConfig:
    """Privacy and circuit configuration for VPN/onion routing.

    Attributes:
        min_circuit_hops: Minimum number of hops in a circuit
        max_circuit_hops: Maximum number of hops in a circuit
        default_circuit_hops: Default number of hops for new circuits
        max_circuits: Maximum number of concurrent circuits
        max_circuits_per_level: Maximum circuits per privacy level
        circuit_lifetime_minutes: Circuit lifetime before rotation (minutes)
        circuit_lifetime_hours: Circuit lifetime in hours (for compatibility)
        key_derivation_length: Key derivation output length in bytes
        key_derivation_salt: Salt for key derivation
        key_derivation_info: Info parameter for key derivation
    """
    min_circuit_hops: int = field(default_factory=lambda: get_env_int('FOG_MIN_CIRCUIT_HOPS', 3))
    max_circuit_hops: int = field(default_factory=lambda: get_env_int('FOG_MAX_CIRCUIT_HOPS', 7))
    default_circuit_hops: int = field(default_factory=lambda: get_env_int('FOG_DEFAULT_CIRCUIT_HOPS', 3))

    max_circuits: int = field(default_factory=lambda: get_env_int('FOG_MAX_CIRCUITS', 50))
    max_circuits_per_level: int = field(default_factory=lambda: get_env_int('FOG_MAX_CIRCUITS_PER_LEVEL', 10))

    circuit_lifetime_minutes: int = field(default_factory=lambda: get_env_int('FOG_CIRCUIT_LIFETIME', 30))

    key_derivation_length: int = field(default_factory=lambda: get_env_int('FOG_KEY_DERIVATION_LENGTH', 64))
    key_derivation_salt: bytes = field(default_factory=lambda: os.getenv('FOG_KEY_SALT', 'fog-onion-v1').encode('utf-8'))
    key_derivation_info: bytes = field(default_factory=lambda: os.getenv('FOG_KEY_INFO', 'circuit-keys').encode('utf-8'))

    @property
    def circuit_lifetime_hours(self) -> int:
        """Convert circuit lifetime to hours for compatibility."""
        return self.circuit_lifetime_minutes // 60


@dataclass
class PerformanceConfig:
    """Performance tuning and resource limits.

    Attributes:
        max_concurrent_tasks: Maximum concurrent task execution
        task_queue_size: Maximum task queue size
        worker_threads: Number of worker threads
        connection_pool_size: Database/cache connection pool size
        cache_ttl_seconds: Default cache TTL in seconds
        cache_max_size: Maximum cache size in entries
        batch_size: Default batch processing size
        chunk_size: Default chunk size for data processing
    """
    max_concurrent_tasks: int = field(default_factory=lambda: get_env_int('FOG_MAX_CONCURRENT_TASKS', 100))
    task_queue_size: int = field(default_factory=lambda: get_env_int('FOG_TASK_QUEUE_SIZE', 1000))
    worker_threads: int = field(default_factory=lambda: get_env_int('FOG_WORKER_THREADS', 4))

    connection_pool_size: int = field(default_factory=lambda: get_env_int('FOG_CONNECTION_POOL_SIZE', 20))

    cache_ttl_seconds: int = field(default_factory=lambda: get_env_int('FOG_CACHE_TTL', 300))
    cache_max_size: int = field(default_factory=lambda: get_env_int('FOG_CACHE_MAX_SIZE', 1000))

    batch_size: int = field(default_factory=lambda: get_env_int('FOG_BATCH_SIZE', 100))
    chunk_size: int = field(default_factory=lambda: get_env_int('FOG_CHUNK_SIZE', 1024))


@dataclass
class Config:
    """Master configuration object containing all sub-configurations.

    This is the main configuration instance that should be imported and used
    throughout the fog-compute project.

    Attributes:
        network: Network and connectivity settings
        betanet: BetaNet-specific settings
        redis: Redis cache/queue settings
        tokenomics: Token economics and rewards settings
        privacy: Privacy and circuit routing settings
        performance: Performance tuning settings
    """
    network: NetworkConfig = field(default_factory=NetworkConfig)
    betanet: BetanetConfig = field(default_factory=BetanetConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    tokenomics: TokenomicsConfig = field(default_factory=TokenomicsConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    def to_dict(self) -> dict:
        """Convert configuration to dictionary representation."""
        return {
            'network': self.network.__dict__,
            'betanet': self.betanet.__dict__,
            'redis': self.redis.__dict__,
            'tokenomics': self.tokenomics.__dict__,
            'privacy': {
                k: v.decode('utf-8') if isinstance(v, bytes) else v
                for k, v in self.privacy.__dict__.items()
            },
            'performance': self.performance.__dict__,
        }

    def get_summary(self) -> str:
        """Get a human-readable configuration summary."""
        lines = [
            "Fog-Compute Configuration Summary",
            "=" * 50,
            "",
            "Network Configuration:",
            f"  BetaNet: {self.network.betanet_api_url}",
            f"  BitChat: {self.network.bitchat_api_url}",
            f"  Redis: {self.network.redis_url}",
            f"  API Gateway: {self.network.api_gateway_url}",
            "",
            "Tokenomics:",
            f"  Reward Rate: {self.tokenomics.reward_rate_per_hour} tokens/hour",
            f"  Transfer Fee: {self.tokenomics.transfer_fee_percentage * 100}%",
            "",
            "Privacy:",
            f"  Circuit Hops: {self.privacy.min_circuit_hops}-{self.privacy.max_circuit_hops}",
            f"  Max Circuits: {self.privacy.max_circuits}",
            f"  Circuit Lifetime: {self.privacy.circuit_lifetime_minutes} minutes",
            "",
            "Performance:",
            f"  Max Concurrent Tasks: {self.performance.max_concurrent_tasks}",
            f"  Worker Threads: {self.performance.worker_threads}",
            f"  Connection Pool: {self.performance.connection_pool_size}",
        ]
        return "\n".join(lines)


# Global configuration instance
config = Config()


# Convenience functions for backward compatibility
def get_redis_url() -> str:
    """Get Redis connection URL (backward compatible)."""
    return config.network.redis_url


def get_betanet_api_url() -> str:
    """Get BetaNet API URL (backward compatible)."""
    return config.network.betanet_api_url


def get_bitchat_api_url() -> str:
    """Get BitChat API URL (backward compatible)."""
    return config.network.bitchat_api_url


__all__ = [
    'config',
    'Config',
    'NetworkConfig',
    'BetanetConfig',
    'RedisConfig',
    'TokenomicsConfig',
    'PrivacyConfig',
    'PerformanceConfig',
    'get_redis_url',
    'get_betanet_api_url',
    'get_bitchat_api_url',
]
