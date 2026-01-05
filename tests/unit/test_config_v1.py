"""
Unit tests for new v1.0 configuration options.
"""

import pytest
from waitless.config import StabilizationConfig


class TestWebSocketSSEConfig:
    """Tests for WebSocket/SSE configuration options."""
    
    def test_track_websocket_default_false(self):
        """Test that track_websocket defaults to False."""
        config = StabilizationConfig()
        assert config.track_websocket is False
    
    def test_track_websocket_can_be_enabled(self):
        """Test that track_websocket can be enabled."""
        config = StabilizationConfig(track_websocket=True)
        assert config.track_websocket is True
    
    def test_track_sse_default_false(self):
        """Test that track_sse defaults to False."""
        config = StabilizationConfig()
        assert config.track_sse is False
    
    def test_track_sse_can_be_enabled(self):
        """Test that track_sse can be enabled."""
        config = StabilizationConfig(track_sse=True)
        assert config.track_sse is True
    
    def test_websocket_quiet_time_default(self):
        """Test that websocket_quiet_time has default value."""
        config = StabilizationConfig()
        assert config.websocket_quiet_time == 0.5
    
    def test_websocket_quiet_time_customizable(self):
        """Test that websocket_quiet_time can be customized."""
        config = StabilizationConfig(websocket_quiet_time=1.0)
        assert config.websocket_quiet_time == 1.0


class TestFrameworkHooksConfig:
    """Tests for framework hooks configuration."""
    
    def test_framework_hooks_default_empty(self):
        """Test that framework_hooks defaults to empty list."""
        config = StabilizationConfig()
        assert config.framework_hooks == []
    
    def test_framework_hooks_single(self):
        """Test setting single framework hook."""
        config = StabilizationConfig(framework_hooks=['react'])
        assert config.framework_hooks == ['react']
    
    def test_framework_hooks_multiple(self):
        """Test setting multiple framework hooks."""
        config = StabilizationConfig(framework_hooks=['react', 'angular', 'vue'])
        assert 'react' in config.framework_hooks
        assert 'angular' in config.framework_hooks
        assert 'vue' in config.framework_hooks
    
    def test_framework_hooks_list_isolation(self):
        """Test that framework_hooks from with_overrides is isolated."""
        config = StabilizationConfig(framework_hooks=['react'])
        new_config = config.with_overrides(framework_hooks=['angular'])
        # When using with_overrides, the list should be copied
        assert new_config.framework_hooks == ['angular']
        assert config.framework_hooks == ['react']


class TestIframeConfig:
    """Tests for iframe configuration options."""
    
    def test_track_iframes_default_false(self):
        """Test that track_iframes defaults to False."""
        config = StabilizationConfig()
        assert config.track_iframes is False
    
    def test_track_iframes_can_be_enabled(self):
        """Test that track_iframes can be enabled."""
        config = StabilizationConfig(track_iframes=True)
        assert config.track_iframes is True


class TestConfigWithOverrides:
    """Tests for with_overrides method with new options."""
    
    def test_override_track_websocket(self):
        """Test overriding track_websocket."""
        config = StabilizationConfig()
        new_config = config.with_overrides(track_websocket=True)
        assert new_config.track_websocket is True
        assert config.track_websocket is False  # Original unchanged
    
    def test_override_track_sse(self):
        """Test overriding track_sse."""
        config = StabilizationConfig()
        new_config = config.with_overrides(track_sse=True)
        assert new_config.track_sse is True
    
    def test_override_framework_hooks(self):
        """Test overriding framework_hooks."""
        config = StabilizationConfig()
        new_config = config.with_overrides(framework_hooks=['vue'])
        assert new_config.framework_hooks == ['vue']
    
    def test_override_track_iframes(self):
        """Test overriding track_iframes."""
        config = StabilizationConfig()
        new_config = config.with_overrides(track_iframes=True)
        assert new_config.track_iframes is True
    
    def test_multiple_overrides(self):
        """Test multiple overrides at once."""
        config = StabilizationConfig()
        new_config = config.with_overrides(
            track_websocket=True,
            track_sse=True,
            framework_hooks=['react'],
            track_iframes=True,
        )
        assert new_config.track_websocket is True
        assert new_config.track_sse is True
        assert new_config.framework_hooks == ['react']
        assert new_config.track_iframes is True


class TestAllNewOptionsInConfig:
    """Test that all new options work together."""
    
    def test_full_v1_config(self):
        """Test creating a full v1.0 config with all new options."""
        config = StabilizationConfig(
            timeout=15,
            track_websocket=True,
            track_sse=True,
            websocket_quiet_time=0.3,
            framework_hooks=['react', 'angular'],
            track_iframes=True,
            strictness='strict',
        )
        
        assert config.timeout == 15
        assert config.track_websocket is True
        assert config.track_sse is True
        assert config.websocket_quiet_time == 0.3
        assert config.framework_hooks == ['react', 'angular']
        assert config.track_iframes is True
        assert config.strictness == 'strict'
