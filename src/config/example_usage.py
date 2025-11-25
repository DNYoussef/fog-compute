"""
Example usage of the centralized configuration system.

This script demonstrates how to use the config module throughout the fog-compute project.
"""

from config import (
    config,
    get_redis_url,
    get_betanet_api_url,
    get_bitchat_api_url,
)


def example_network_config():
    """Example: Accessing network configuration."""
    print("=== Network Configuration ===")

    # Access individual network settings
    print(f"BetaNet Host: {config.network.betanet_host}")
    print(f"BetaNet Port: {config.network.betanet_port}")
    print(f"BetaNet API Port: {config.network.betanet_api_port}")

    # Use convenience URL properties
    print(f"Redis URL: {config.network.redis_url}")
    print(f"BetaNet API URL: {config.network.betanet_api_url}")
    print(f"BitChat API URL: {config.network.bitchat_api_url}")
    print(f"API Gateway URL: {config.network.api_gateway_url}")

    # Timeouts and retries
    print(f"Connection Timeout: {config.network.connection_timeout}s")
    print(f"Max Retries: {config.network.max_retries}")
    print()


def example_redis_config():
    """Example: Accessing Redis configuration."""
    print("=== Redis Configuration ===")

    print(f"Redis Host: {config.redis.host}")
    print(f"Redis Port: {config.redis.port}")
    print(f"Redis DB: {config.redis.db}")
    print(f"Connection URL: {config.redis.connection_url}")
    print(f"Max Connections: {config.redis.max_connections}")
    print(f"Socket Timeout: {config.redis.socket_timeout}s")
    print()


def example_betanet_config():
    """Example: Accessing BetaNet-specific configuration."""
    print("=== BetaNet Configuration ===")

    print(f"Server Host: {config.betanet.server_host}")
    print(f"Server Port: {config.betanet.server_port}")
    print(f"API Port: {config.betanet.api_port}")
    print(f"Max Peers: {config.betanet.max_peers}")
    print(f"Discovery Interval: {config.betanet.peer_discovery_interval}s")
    print(f"Heartbeat Interval: {config.betanet.heartbeat_interval}s")
    print(f"Relay Enabled: {config.betanet.relay_enabled}")
    print(f"Relay Lottery: {config.betanet.relay_lottery_enabled}")
    print()


def example_tokenomics_config():
    """Example: Accessing tokenomics configuration."""
    print("=== Tokenomics Configuration ===")

    print(f"Reward Rate: {config.tokenomics.reward_rate_per_hour} tokens/hour")
    print(f"Staking Multiplier: {config.tokenomics.staking_reward_multiplier}x")
    print(f"Performance Bonus Threshold: {config.tokenomics.performance_bonus_threshold}")
    print(f"Performance Bonus Rate: {config.tokenomics.performance_bonus_rate}")
    print(f"Transfer Fee: {config.tokenomics.transfer_fee_percentage * 100}%")
    print(f"Max Transfer: {config.tokenomics.max_transfer_amount} tokens")
    print(f"Failure Rate Threshold: {config.tokenomics.failure_rate_threshold * 100}%")
    print()


def example_privacy_config():
    """Example: Accessing privacy and circuit configuration."""
    print("=== Privacy Configuration ===")

    print(f"Min Circuit Hops: {config.privacy.min_circuit_hops}")
    print(f"Max Circuit Hops: {config.privacy.max_circuit_hops}")
    print(f"Default Circuit Hops: {config.privacy.default_circuit_hops}")
    print(f"Max Circuits: {config.privacy.max_circuits}")
    print(f"Max Circuits per Level: {config.privacy.max_circuits_per_level}")
    print(f"Circuit Lifetime: {config.privacy.circuit_lifetime_minutes} minutes")
    print(f"Circuit Lifetime (hours): {config.privacy.circuit_lifetime_hours} hours")
    print(f"Key Derivation Length: {config.privacy.key_derivation_length} bytes")
    print()


def example_performance_config():
    """Example: Accessing performance configuration."""
    print("=== Performance Configuration ===")

    print(f"Max Concurrent Tasks: {config.performance.max_concurrent_tasks}")
    print(f"Task Queue Size: {config.performance.task_queue_size}")
    print(f"Worker Threads: {config.performance.worker_threads}")
    print(f"Connection Pool Size: {config.performance.connection_pool_size}")
    print(f"Cache TTL: {config.performance.cache_ttl_seconds}s")
    print(f"Cache Max Size: {config.performance.cache_max_size} entries")
    print(f"Batch Size: {config.performance.batch_size}")
    print(f"Chunk Size: {config.performance.chunk_size} bytes")
    print()


def example_backward_compatibility():
    """Example: Using backward compatibility functions."""
    print("=== Backward Compatibility ===")

    redis_url = get_redis_url()
    betanet_url = get_betanet_api_url()
    bitchat_url = get_bitchat_api_url()

    print(f"Redis URL (legacy): {redis_url}")
    print(f"BetaNet URL (legacy): {betanet_url}")
    print(f"BitChat URL (legacy): {bitchat_url}")
    print()


def example_practical_usage():
    """Example: Practical usage in real code."""
    print("=== Practical Usage Examples ===")

    # Example 1: Setting up Redis connection
    print("1. Redis Connection Setup:")
    print(f"   import redis")
    print(f"   r = redis.from_url('{config.network.redis_url}')")
    print()

    # Example 2: Creating BetaNet API client
    print("2. BetaNet API Client:")
    print(f"   import httpx")
    print(f"   client = httpx.AsyncClient(")
    print(f"       base_url='{config.network.betanet_api_url}',")
    print(f"       timeout={config.network.request_timeout}")
    print(f"   )")
    print()

    # Example 3: Circuit creation with privacy settings
    print("3. Circuit Creation:")
    print(f"   circuit = await build_circuit(")
    print(f"       num_hops={config.privacy.default_circuit_hops},")
    print(f"       lifetime_minutes={config.privacy.circuit_lifetime_minutes}")
    print(f"   )")
    print()

    # Example 4: Token reward distribution
    print("4. Token Reward Distribution:")
    print(f"   reward = calculate_reward(")
    print(f"       hours_worked=8,")
    print(f"       rate={config.tokenomics.reward_rate_per_hour}")
    print(f"   )")
    print(f"   # Result: 8 * {config.tokenomics.reward_rate_per_hour} = {8 * config.tokenomics.reward_rate_per_hour} tokens")
    print()


def example_config_export():
    """Example: Exporting configuration to dictionary."""
    print("=== Configuration Export ===")

    config_dict = config.to_dict()
    print("Configuration as dictionary:")
    print(f"  Network keys: {list(config_dict['network'].keys())}")
    print(f"  Tokenomics keys: {list(config_dict['tokenomics'].keys())}")
    print(f"  Privacy keys: {list(config_dict['privacy'].keys())}")
    print()


def example_config_summary():
    """Example: Getting configuration summary."""
    print("=== Configuration Summary ===")
    print(config.get_summary())
    print()


if __name__ == "__main__":
    # Run all examples
    example_network_config()
    example_redis_config()
    example_betanet_config()
    example_tokenomics_config()
    example_privacy_config()
    example_performance_config()
    example_backward_compatibility()
    example_practical_usage()
    example_config_export()
    example_config_summary()

    print("=" * 60)
    print("Configuration module usage examples complete!")
    print("=" * 60)
