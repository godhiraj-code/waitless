"""
Unit tests for waitless configuration.
"""

import pytest
import warnings
from waitless.config import StabilizationConfig, DEFAULT_CONFIG
from waitless.exceptions import ConfigurationError


class TestStabilizationConfig:
    """Tests for StabilizationConfig dataclass."""
    
    def test_default_values(self):
        """Test that defaults are sensible."""
        config = StabilizationConfig()
        
        assert config.timeout == 10.0
        assert config.dom_settle_time == 0.1
        assert config.network_idle_threshold == 0
        assert config.animation_detection is True
        assert config.strictness == 'normal'
        assert config.debug_mode is False
        assert config.poll_interval == 0.05
    
    def test_custom_values(self):
        """Test custom configuration."""
        config = StabilizationConfig(
            timeout=5.0,
            strictness='strict',
            debug_mode=True,
        )
        
        assert config.timeout == 5.0
        assert config.strictness == 'strict'
        assert config.debug_mode is True
    
    def test_invalid_timeout_zero(self):
        """Test that zero timeout raises error."""
        with pytest.raises(ConfigurationError) as exc:
            StabilizationConfig(timeout=0)
        
        assert "timeout must be positive" in str(exc.value)
    
    def test_invalid_timeout_negative(self):
        """Test that negative timeout raises error."""
        with pytest.raises(ConfigurationError):
            StabilizationConfig(timeout=-1)
    
    def test_invalid_strictness(self):
        """Test that invalid strictness raises error."""
        with pytest.raises(ConfigurationError):
            StabilizationConfig(strictness='invalid')
    
    def test_invalid_poll_interval(self):
        """Test that invalid poll interval raises error."""
        with pytest.raises(ConfigurationError):
            StabilizationConfig(poll_interval=0)
        
        with pytest.raises(ConfigurationError):
            StabilizationConfig(poll_interval=-0.1)
    
    def test_poll_interval_exceeds_timeout(self):
        """Test poll_interval cannot exceed timeout."""
        with pytest.raises(ConfigurationError):
            StabilizationConfig(timeout=1, poll_interval=2)
    
    def test_very_high_timeout_warning(self):
        """Test that very high timeout generates warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            StabilizationConfig(timeout=120)
            
            assert len(w) == 1
            assert "very high" in str(w[0].message)
    
    def test_with_overrides(self):
        """Test with_overrides creates new config."""
        config = StabilizationConfig(timeout=10, debug_mode=False)
        new_config = config.with_overrides(timeout=5, debug_mode=True)
        
        # Original unchanged
        assert config.timeout == 10
        assert config.debug_mode is False
        
        # New config has overrides
        assert new_config.timeout == 5
        assert new_config.debug_mode is True
    
    def test_factory_strict(self):
        """Test strict factory method."""
        config = StabilizationConfig.strict()
        
        assert config.strictness == 'strict'
        assert config.timeout == 5.0
        assert config.animation_detection is True
        assert config.layout_stability is True
    
    def test_factory_relaxed(self):
        """Test relaxed factory method."""
        config = StabilizationConfig.relaxed()
        
        assert config.strictness == 'relaxed'
        assert config.network_idle_threshold == 2
        assert config.animation_detection is False
    
    def test_factory_ci(self):
        """Test CI factory method."""
        config = StabilizationConfig.ci()
        
        assert config.timeout == 15.0
        assert config.debug_mode is True
        assert config.strictness == 'normal'
    
    def test_default_config_singleton(self):
        """Test DEFAULT_CONFIG is valid."""
        assert DEFAULT_CONFIG is not None
        assert DEFAULT_CONFIG.timeout == 10.0
