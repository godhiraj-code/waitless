"""
Waitless configuration management.

Provides sensible defaults with full customization options.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional
from .exceptions import ConfigurationError


StrictnessLevel = Literal['strict', 'normal', 'relaxed']


@dataclass
class StabilizationConfig:
    """
    Configuration for UI stabilization behavior.
    
    Attributes:
        timeout: Maximum time (seconds) to wait for stability. Default 10s.
                 Consider lowering to 5s for faster feedback loops.
        
        dom_settle_time: Time (seconds) DOM must be quiet to be considered stable.
                         Default 0.1s (100ms).
        
        network_idle_threshold: Maximum pending requests allowed for stability.
                                Default 0 (all requests must complete).
                                
                                ⚠️ WARNING: Many apps have background traffic:
                                - Analytics calls
                                - Long polling  
                                - Feature flags
                                - WebSocket heartbeats
                                
                                If your tests timeout frequently, try setting this to 1-2.
        
        animation_detection: Whether to wait for CSS animations/transitions.
                             Default True. Disable for apps with infinite animations.
        
        layout_stability: Whether to wait for element positions to stabilize.
                          Default True in 'strict' mode.
        
        strictness: Overall strictness level.
                    - 'strict': All signals must be stable (recommended)
                    - 'normal': DOM + Network only (faster)
                    - 'relaxed': DOM only (fastest, least reliable)
        
        debug_mode: Enable verbose logging for troubleshooting.
                    Default False.
        
        poll_interval: How often to check stability (seconds).
                       Default 0.05s (50ms). Lower = more responsive but more CPU.
        
        reinject_on_navigation: Auto-reinject instrumentation after navigation.
                                Default True.
    """
    
    timeout: float = 10.0
    dom_settle_time: float = 0.1
    network_idle_threshold: int = 0
    animation_detection: bool = True
    layout_stability: bool = True
    strictness: StrictnessLevel = 'normal'
    debug_mode: bool = False
    poll_interval: float = 0.05
    reinject_on_navigation: bool = True
    
    def __post_init__(self):
        """Validate configuration values."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate all configuration values."""
        if self.timeout <= 0:
            raise ConfigurationError(f"timeout must be positive, got {self.timeout}")
        
        if self.timeout > 60:
            import warnings
            warnings.warn(
                f"timeout of {self.timeout}s is very high. "
                "Consider investigating root cause of slow stability.",
                UserWarning
            )
        
        if self.dom_settle_time < 0:
            raise ConfigurationError(
                f"dom_settle_time must be non-negative, got {self.dom_settle_time}"
            )
        
        if self.network_idle_threshold < 0:
            raise ConfigurationError(
                f"network_idle_threshold must be non-negative, got {self.network_idle_threshold}"
            )
        
        if self.poll_interval <= 0:
            raise ConfigurationError(
                f"poll_interval must be positive, got {self.poll_interval}"
            )
        
        if self.poll_interval > self.timeout:
            raise ConfigurationError(
                f"poll_interval ({self.poll_interval}) cannot exceed timeout ({self.timeout})"
            )
        
        if self.strictness not in ('strict', 'normal', 'relaxed'):
            raise ConfigurationError(
                f"strictness must be 'strict', 'normal', or 'relaxed', got '{self.strictness}'"
            )
    
    def with_overrides(self, **kwargs) -> 'StabilizationConfig':
        """
        Create a new config with some values overridden.
        
        Example:
            new_config = config.with_overrides(timeout=5, debug_mode=True)
        """
        current = {
            'timeout': self.timeout,
            'dom_settle_time': self.dom_settle_time,
            'network_idle_threshold': self.network_idle_threshold,
            'animation_detection': self.animation_detection,
            'layout_stability': self.layout_stability,
            'strictness': self.strictness,
            'debug_mode': self.debug_mode,
            'poll_interval': self.poll_interval,
            'reinject_on_navigation': self.reinject_on_navigation,
        }
        current.update(kwargs)
        return StabilizationConfig(**current)
    
    @classmethod
    def strict(cls) -> 'StabilizationConfig':
        """Factory for strict configuration (all signals, lower timeout)."""
        return cls(
            strictness='strict',
            timeout=5.0,
            animation_detection=True,
            layout_stability=True,
        )
    
    @classmethod
    def relaxed(cls) -> 'StabilizationConfig':
        """Factory for relaxed configuration (DOM only, higher threshold)."""
        return cls(
            strictness='relaxed',
            network_idle_threshold=2,
            animation_detection=False,
            layout_stability=False,
        )
    
    @classmethod
    def ci(cls) -> 'StabilizationConfig':
        """Factory for CI environments (longer timeout, verbose logging)."""
        return cls(
            timeout=15.0,
            debug_mode=True,
            strictness='normal',
        )


DEFAULT_CONFIG = StabilizationConfig()
