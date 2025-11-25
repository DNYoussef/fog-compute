"""
Unit tests for the centralized configuration module.

Tests configuration loading, defaults, environment variable overrides, and URL generation.
"""

import os
import unittest
from unittest.mock import patch

from config import (
    Config,
    NetworkConfig,
    BetanetConfig,
    RedisConfig,
    TokenomicsConfig,
    PrivacyConfig,
    PerformanceConfig,
    config,
    get_redis_url,
    get_betanet_api_url,
    get_bitchat_api_url,
)


class TestNetworkConfig(unittest.TestCase):
    """Test NetworkConfig class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        net_config = NetworkConfig()

        self.assertEqual(net_config.betanet_host, '127.0.0.1')
        self.assertEqual(net_config.betanet_port, 9000)
        self.assertEqual(net_config.betanet_api_port, 8443)
        self.assertEqual(net_config.redis_host, 'localhost')
        self.assertEqual(net_config.redis_port, 6379)
        self.assertEqual(net_config.api_port, 8080)
        self.assertEqual(net_config.bitchat_port, 8000)

    def test_redis_url_generation(self):
        """Test Redis URL property."""
        net_config = NetworkConfig()
        expected_url = "redis://localhost:6379"
        self.assertEqual(net_config.redis_url, expected_url)

    def test_betanet_api_url_generation(self):
        """Test BetaNet API URL property."""
        net_config = NetworkConfig()
        expected_url = "http://127.0.0.1:8443"
        self.assertEqual(net_config.betanet_api_url, expected_url)

    def test_bitchat_api_url_generation(self):
        """Test BitChat API URL property."""
        net_config = NetworkConfig()
        expected_url = "http://localhost:8000"
        self.assertEqual(net_config.bitchat_api_url, expected_url)

    def test_api_gateway_url_generation(self):
        """Test API gateway URL property."""
        net_config = NetworkConfig()
        expected_url = "http://localhost:8080"
        self.assertEqual(net_config.api_gateway_url, expected_url)

    @patch.dict(os.environ, {
        'FOG_BETANET_HOST': '10.0.0.5',
        'FOG_BETANET_PORT': '9001',
        'FOG_REDIS_HOST': 'redis.internal',
        'FOG_REDIS_PORT': '6380',
    })
    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        net_config = NetworkConfig()

        self.assertEqual(net_config.betanet_host, '10.0.0.5')
        self.assertEqual(net_config.betanet_port, 9001)
        self.assertEqual(net_config.redis_host, 'redis.internal')
        self.assertEqual(net_config.redis_port, 6380)


class TestBetanetConfig(unittest.TestCase):
    """Test BetanetConfig class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        betanet_config = BetanetConfig()

        self.assertEqual(betanet_config.server_host, '127.0.0.1')
        self.assertEqual(betanet_config.server_port, 9000)
        self.assertEqual(betanet_config.api_port, 8443)
        self.assertEqual(betanet_config.max_peers, 100)
        self.assertTrue(betanet_config.relay_enabled)
        self.assertTrue(betanet_config.relay_lottery_enabled)


class TestRedisConfig(unittest.TestCase):
    """Test RedisConfig class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        redis_config = RedisConfig()

        self.assertEqual(redis_config.host, 'localhost')
        self.assertEqual(redis_config.port, 6379)
        self.assertEqual(redis_config.db, 0)
        self.assertIsNone(redis_config.password)
        self.assertEqual(redis_config.max_connections, 50)

    def test_connection_url_without_password(self):
        """Test connection URL generation without password."""
        redis_config = RedisConfig()
        expected_url = "redis://localhost:6379/0"
        self.assertEqual(redis_config.connection_url, expected_url)

    @patch.dict(os.environ, {'FOG_REDIS_PASSWORD': 'secret123'})
    def test_connection_url_with_password(self):
        """Test connection URL generation with password."""
        redis_config = RedisConfig()
        expected_url = "redis://:secret123@localhost:6379/0"
        self.assertEqual(redis_config.connection_url, expected_url)


class TestTokenomicsConfig(unittest.TestCase):
    """Test TokenomicsConfig class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        tokenomics_config = TokenomicsConfig()

        self.assertEqual(tokenomics_config.reward_rate_per_hour, 10.0)
        self.assertEqual(tokenomics_config.staking_reward_multiplier, 1.5)
        self.assertEqual(tokenomics_config.performance_bonus_threshold, 0.95)
        self.assertEqual(tokenomics_config.transfer_fee_percentage, 0.01)
        self.assertEqual(tokenomics_config.max_transfer_amount, 10000.0)

    @patch.dict(os.environ, {
        'FOG_REWARD_RATE': '15.5',
        'FOG_TRANSFER_FEE': '0.02',
    })
    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        tokenomics_config = TokenomicsConfig()

        self.assertEqual(tokenomics_config.reward_rate_per_hour, 15.5)
        self.assertEqual(tokenomics_config.transfer_fee_percentage, 0.02)


class TestPrivacyConfig(unittest.TestCase):
    """Test PrivacyConfig class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        privacy_config = PrivacyConfig()

        self.assertEqual(privacy_config.min_circuit_hops, 3)
        self.assertEqual(privacy_config.max_circuit_hops, 7)
        self.assertEqual(privacy_config.default_circuit_hops, 3)
        self.assertEqual(privacy_config.max_circuits, 50)
        self.assertEqual(privacy_config.circuit_lifetime_minutes, 30)
        self.assertEqual(privacy_config.key_derivation_length, 64)

    def test_circuit_lifetime_hours_property(self):
        """Test circuit_lifetime_hours property calculation."""
        privacy_config = PrivacyConfig()
        expected_hours = 30 // 60
        self.assertEqual(privacy_config.circuit_lifetime_hours, expected_hours)

    def test_key_derivation_defaults(self):
        """Test key derivation default values."""
        privacy_config = PrivacyConfig()

        self.assertEqual(privacy_config.key_derivation_salt, b'fog-onion-v1')
        self.assertEqual(privacy_config.key_derivation_info, b'circuit-keys')


class TestPerformanceConfig(unittest.TestCase):
    """Test PerformanceConfig class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        perf_config = PerformanceConfig()

        self.assertEqual(perf_config.max_concurrent_tasks, 100)
        self.assertEqual(perf_config.task_queue_size, 1000)
        self.assertEqual(perf_config.worker_threads, 4)
        self.assertEqual(perf_config.connection_pool_size, 20)
        self.assertEqual(perf_config.cache_ttl_seconds, 300)
        self.assertEqual(perf_config.batch_size, 100)


class TestConfig(unittest.TestCase):
    """Test master Config class."""

    def test_config_initialization(self):
        """Test that Config initializes all sub-configs."""
        test_config = Config()

        self.assertIsInstance(test_config.network, NetworkConfig)
        self.assertIsInstance(test_config.betanet, BetanetConfig)
        self.assertIsInstance(test_config.redis, RedisConfig)
        self.assertIsInstance(test_config.tokenomics, TokenomicsConfig)
        self.assertIsInstance(test_config.privacy, PrivacyConfig)
        self.assertIsInstance(test_config.performance, PerformanceConfig)

    def test_to_dict(self):
        """Test configuration export to dictionary."""
        test_config = Config()
        config_dict = test_config.to_dict()

        self.assertIn('network', config_dict)
        self.assertIn('betanet', config_dict)
        self.assertIn('redis', config_dict)
        self.assertIn('tokenomics', config_dict)
        self.assertIn('privacy', config_dict)
        self.assertIn('performance', config_dict)

        # Check that nested dictionaries contain expected keys
        self.assertIn('betanet_host', config_dict['network'])
        self.assertIn('reward_rate_per_hour', config_dict['tokenomics'])
        self.assertIn('min_circuit_hops', config_dict['privacy'])

    def test_get_summary(self):
        """Test configuration summary generation."""
        test_config = Config()
        summary = test_config.get_summary()

        self.assertIsInstance(summary, str)
        self.assertIn('Fog-Compute Configuration Summary', summary)
        self.assertIn('Network Configuration:', summary)
        self.assertIn('Tokenomics:', summary)
        self.assertIn('Privacy:', summary)


class TestGlobalConfig(unittest.TestCase):
    """Test global config instance."""

    def test_global_config_exists(self):
        """Test that global config instance is available."""
        self.assertIsInstance(config, Config)

    def test_config_is_singleton(self):
        """Test that config behaves like a singleton."""
        from config import config as config2
        self.assertIs(config, config2)


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility functions."""

    def test_get_redis_url(self):
        """Test get_redis_url backward compatibility function."""
        redis_url = get_redis_url()
        self.assertIn('redis://', redis_url)
        self.assertIn('6379', redis_url)

    def test_get_betanet_api_url(self):
        """Test get_betanet_api_url backward compatibility function."""
        betanet_url = get_betanet_api_url()
        self.assertIn('http://', betanet_url)
        self.assertIn('8443', betanet_url)

    def test_get_bitchat_api_url(self):
        """Test get_bitchat_api_url backward compatibility function."""
        bitchat_url = get_bitchat_api_url()
        self.assertIn('http://', bitchat_url)
        self.assertIn('8000', bitchat_url)


class TestEnvironmentVariableParsing(unittest.TestCase):
    """Test environment variable parsing utilities."""

    @patch.dict(os.environ, {'TEST_INT': '42'})
    def test_int_parsing(self):
        """Test integer environment variable parsing."""
        from config import get_env_int
        value = get_env_int('TEST_INT', 0)
        self.assertEqual(value, 42)

    @patch.dict(os.environ, {'TEST_INT': 'not_a_number'})
    def test_int_parsing_invalid(self):
        """Test integer parsing with invalid value."""
        from config import get_env_int
        value = get_env_int('TEST_INT', 999)
        self.assertEqual(value, 999)  # Should return default

    @patch.dict(os.environ, {'TEST_FLOAT': '3.14'})
    def test_float_parsing(self):
        """Test float environment variable parsing."""
        from config import get_env_float
        value = get_env_float('TEST_FLOAT', 0.0)
        self.assertEqual(value, 3.14)

    @patch.dict(os.environ, {'TEST_BOOL': 'true'})
    def test_bool_parsing_true(self):
        """Test boolean parsing for true values."""
        from config import get_env_bool
        self.assertTrue(get_env_bool('TEST_BOOL', False))

    @patch.dict(os.environ, {'TEST_BOOL': '1'})
    def test_bool_parsing_one(self):
        """Test boolean parsing for '1'."""
        from config import get_env_bool
        self.assertTrue(get_env_bool('TEST_BOOL', False))

    @patch.dict(os.environ, {'TEST_BOOL': 'false'})
    def test_bool_parsing_false(self):
        """Test boolean parsing for false values."""
        from config import get_env_bool
        self.assertFalse(get_env_bool('TEST_BOOL', True))


if __name__ == '__main__':
    unittest.main()
