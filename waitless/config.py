"""
Waitless configuration management.

Provides sensible defaults with full customization options.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, List
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
                         Default 0.1s (100ms). This is a FALLBACK - mutation rate
                         is the primary check for DOM stability.
        
        mutation_rate_threshold: Maximum mutations per second for DOM to be stable.
                                 Default 50/sec. This allows animated sites (typewriter
                                 effects ~30/sec) while catching loading bursts (100+/sec).
        
        network_idle_threshold: Maximum pending requests allowed for stability.
                                Default 2 (allows background analytics/polling).
                                Set to 0 for strict mode if all requests must complete.
        
        animation_detection: Whether to wait for CSS animations/transitions.
                             Default True. Disable for apps with infinite animations.
        
        layout_stability: Whether to wait for element positions to stabilize.
                          Default True in 'strict' mode.
        
        strictness: Overall strictness level.
                    - 'strict': All signals must be stable (recommended for CI)
                    - 'normal': DOM + Network only (default)
                    - 'relaxed': DOM only (fastest)
        
        debug_mode: Enable verbose logging for troubleshooting.
                    Default False.
        
        poll_interval: How often to check stability (seconds).
                       Default 0.05s (50ms). Lower = more responsive but more CPU.
        
        reinject_on_navigation: Auto-reinject instrumentation after navigation.
                                Default True.
        
        track_websocket: Whether to monitor WebSocket connections.
                         Default False. Enable for apps using WebSocket.
        
        track_sse: Whether to monitor Server-Sent Events (EventSource).
                   Default False. Enable for apps using SSE.
        
        websocket_quiet_time: Time (seconds) WS/SSE must be quiet for stability.
                              Default 0.5s. Only used when track_websocket/track_sse is True.
        
        framework_hooks: List of framework adapters to use for stability detection.
                         Options: 'react', 'angular', 'vue'. Default empty (auto-detect off).
                         When specified, waitless will inject framework-specific hooks.
        
        track_iframes: Whether to inject instrumentation into same-origin iframes.
                       Default False. Cross-origin iframes cannot be accessed.
    """
    
    timeout: float = 10.0
    dom_settle_time: float = 0.1
    mutation_rate_threshold: float = 50.0  # mutations/sec - allows animations
    network_idle_threshold: int = 2  # Allow background traffic
    animation_detection: bool = True
    layout_stability: bool = True
    strictness: StrictnessLevel = 'normal'
    debug_mode: bool = False
    poll_interval: float = 0.05
    reinject_on_navigation: bool = True
    track_websocket: bool = False  # WebSocket monitoring (opt-in)
    track_sse: bool = False        # SSE/EventSource monitoring (opt-in)
    websocket_quiet_time: float = 0.5  # Seconds of WS/SSE silence for stability
    framework_hooks: List[str] = field(default_factory=list)  # ['react', 'angular', 'vue']
    track_iframes: bool = False  # Same-origin iframe monitoring (opt-in)
    
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
            'mutation_rate_threshold': self.mutation_rate_threshold,
            'network_idle_threshold': self.network_idle_threshold,
            'animation_detection': self.animation_detection,
            'layout_stability': self.layout_stability,
            'strictness': self.strictness,
            'debug_mode': self.debug_mode,
            'poll_interval': self.poll_interval,
            'reinject_on_navigation': self.reinject_on_navigation,
            'track_websocket': self.track_websocket,
            'track_sse': self.track_sse,
            'websocket_quiet_time': self.websocket_quiet_time,
            'framework_hooks': self.framework_hooks.copy(),
            'track_iframes': self.track_iframes,
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
