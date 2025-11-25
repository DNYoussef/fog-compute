# Fog-Compute Centralized Configuration

This directory contains the centralized configuration system for the fog-compute project.

## Overview

All hardcoded network addresses, ports, and magic numbers have been consolidated into a single configuration module. This provides:

- **Centralized Management**: All configuration in one place
- **Environment-Aware**: Load from environment variables or use sensible defaults
- **Type-Safe**: Strong typing with dataclasses and type hints
- **Easy Access**: Simple import and use throughout the codebase
- **Backward Compatible**: Convenience functions for legacy code

## Usage

### Basic Usage

```python
from config import config

# Access network settings
redis_url = config.network.redis_url
betanet_host = config.network.betanet_host
betanet_port = config.network.betanet_port

# Access tokenomics settings
reward_rate = config.tokenomics.reward_rate_per_hour
transfer_fee = config.tokenomics.transfer_fee_percentage

# Access privacy settings
circuit_hops = config.privacy.min_circuit_hops
max_circuits = config.privacy.max_circuits
```

### Using Convenience URLs

```python
from config import config

# Get fully formed URLs
redis_connection = config.network.redis_url
# "redis://localhost:6379"

betanet_api = config.network.betanet_api_url
# "http://127.0.0.1:8443"

bitchat_api = config.network.bitchat_api_url
# "http://localhost:8000"
```

### Backward Compatibility

```python
from config import get_redis_url, get_betanet_api_url

# Legacy code can use these functions
redis_url = get_redis_url()
betanet_url = get_betanet_api_url()
```

## Environment Variables

Configure the system using environment variables:

### Network Configuration

- `FOG_BETANET_HOST`: BetaNet server host (default: 127.0.0.1)
- `FOG_BETANET_PORT`: BetaNet transport port (default: 9000)
- `FOG_BETANET_API_PORT`: BetaNet HTTP API port (default: 8443)
- `FOG_REDIS_HOST`: Redis server host (default: localhost)
- `FOG_REDIS_PORT`: Redis server port (default: 6379)
- `FOG_API_HOST`: API gateway host (default: localhost)
- `FOG_API_PORT`: API gateway port (default: 8080)
- `FOG_BITCHAT_HOST`: BitChat server host (default: localhost)
- `FOG_BITCHAT_PORT`: BitChat server port (default: 8000)

### Tokenomics Configuration

- `FOG_REWARD_RATE`: Token reward rate per hour (default: 10.0)
- `FOG_STAKING_MULTIPLIER`: Staking reward multiplier (default: 1.5)
- `FOG_TRANSFER_FEE`: Transfer fee percentage (default: 0.01)
- `FOG_MAX_TRANSFER`: Maximum transfer amount (default: 10000.0)

### Privacy Configuration

- `FOG_MIN_CIRCUIT_HOPS`: Minimum circuit hops (default: 3)
- `FOG_MAX_CIRCUIT_HOPS`: Maximum circuit hops (default: 7)
- `FOG_MAX_CIRCUITS`: Maximum concurrent circuits (default: 50)
- `FOG_CIRCUIT_LIFETIME`: Circuit lifetime in minutes (default: 30)

### Performance Configuration

- `FOG_MAX_CONCURRENT_TASKS`: Maximum concurrent tasks (default: 100)
- `FOG_WORKER_THREADS`: Worker thread count (default: 4)
- `FOG_CONNECTION_POOL_SIZE`: Connection pool size (default: 20)
- `FOG_CACHE_TTL`: Cache TTL in seconds (default: 300)

## Configuration Sections

### NetworkConfig

Network and connectivity settings for all services.

**Key Attributes:**
- `betanet_host`, `betanet_port`, `betanet_api_port`
- `redis_host`, `redis_port`
- `api_host`, `api_port`
- `bitchat_host`, `bitchat_port`
- `connection_timeout`, `request_timeout`, `max_retries`

### BetanetConfig

BetaNet-specific transport and relay settings.

**Key Attributes:**
- `server_host`, `server_port`, `api_port`
- `max_peers`, `peer_discovery_interval`, `heartbeat_interval`
- `relay_enabled`, `relay_lottery_enabled`

### RedisConfig

Redis cache and queue configuration.

**Key Attributes:**
- `host`, `port`, `db`, `password`
- `max_connections`, `socket_timeout`
- `decode_responses`

### TokenomicsConfig

Token economics and reward system settings.

**Key Attributes:**
- `reward_rate_per_hour`, `staking_reward_multiplier`
- `performance_bonus_threshold`, `performance_bonus_rate`
- `transfer_fee_percentage`, `max_transfer_amount`

### PrivacyConfig

Privacy and onion routing circuit settings.

**Key Attributes:**
- `min_circuit_hops`, `max_circuit_hops`, `default_circuit_hops`
- `max_circuits`, `max_circuits_per_level`
- `circuit_lifetime_minutes`
- `key_derivation_length`, `key_derivation_salt`, `key_derivation_info`

### PerformanceConfig

Performance tuning and resource limits.

**Key Attributes:**
- `max_concurrent_tasks`, `task_queue_size`, `worker_threads`
- `connection_pool_size`
- `cache_ttl_seconds`, `cache_max_size`
- `batch_size`, `chunk_size`

## Migration Guide

### Before (Hardcoded)

```python
# OLD: Hardcoded values scattered throughout code
redis_url = "redis://localhost:6379"
betanet_port = 8443
circuit_hops = 3
reward_rate = 10.0
```

### After (Centralized)

```python
# NEW: Import from config
from config import config

redis_url = config.network.redis_url
betanet_port = config.network.betanet_api_port
circuit_hops = config.privacy.min_circuit_hops
reward_rate = config.tokenomics.reward_rate_per_hour
```

## Testing

### Development Configuration

For development, use the defaults (no environment variables needed):

```bash
# Defaults will be used
python your_script.py
```

### Production Configuration

Set environment variables for production:

```bash
export FOG_BETANET_HOST=10.0.1.5
export FOG_BETANET_PORT=9000
export FOG_REDIS_HOST=redis.internal
export FOG_REDIS_PORT=6379
export FOG_REWARD_RATE=15.0

python your_script.py
```

### View Configuration

```python
from config import config

# Print configuration summary
print(config.get_summary())

# Export to dictionary
config_dict = config.to_dict()
print(config_dict)
```

## Configuration Summary Output

```
Fog-Compute Configuration Summary
==================================================

Network Configuration:
  BetaNet: http://127.0.0.1:8443
  BitChat: http://localhost:8000
  Redis: redis://localhost:6379
  API Gateway: http://localhost:8080

Tokenomics:
  Reward Rate: 10.0 tokens/hour
  Transfer Fee: 1.0%

Privacy:
  Circuit Hops: 3-7
  Max Circuits: 50
  Circuit Lifetime: 30 minutes

Performance:
  Max Concurrent Tasks: 100
  Worker Threads: 4
  Connection Pool: 20
```

## Files to Update

The following files contain hardcoded values that should be migrated:

### High Priority (Network Addresses)
- `src/fog/caching.py` - Redis URL
- `src/fog/coordinator_enhanced.py` - Redis URL
- `src/fog/coordinator_interface.py` - Port 8080
- `src/p2p/transports/betanet_transport.py` - Port 8443
- `src/p2p/transports/bitchat_transport.py` - Port 8000
- `src/p2p/unified_p2p_config.py` - Multiple ports and hosts
- `src/p2p/unified_p2p_system.py` - Port 8443

### Medium Priority (VPN/Privacy)
- `src/vpn/fog_onion_coordinator.py` - Circuit hops, max circuits
- `src/vpn/onion_circuit_service.py` - Circuit lifetime, max circuits
- `src/vpn/onion_routing.py` - Circuit hops, lifetime
- `src/vpn/transports/betanet_transport.py` - Circuit hops, lifetime

### Lower Priority (Tokenomics)
- `src/tokenomics/fog_tokenomics_service.py` - Reward rates
- `src/idle/harvest_manager.py` - Token rewards
- `src/idle/mobile_resource_manager.py` - Token rewards

## Benefits

1. **Single Source of Truth**: All configuration in one place
2. **Environment-Aware**: Easy to configure for dev/staging/production
3. **Type Safety**: Dataclasses provide type checking
4. **Documentation**: Self-documenting with type hints and docstrings
5. **Testability**: Easy to mock configuration in tests
6. **Maintainability**: Change once, apply everywhere
7. **No Unicode**: Windows-compatible (per project requirements)
