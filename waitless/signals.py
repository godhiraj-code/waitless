"""
Stability signal definitions and combination logic.

Signals are measurable indicators of UI state. This module defines
what signals exist, how to interpret them, and how to combine them
into an overall stability decision.

Note: This module is designed to be a future extension point.
Users may eventually be able to define custom signals.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Any, List, Optional
from .config import StabilizationConfig


class SignalType(Enum):
    """Types of stability signals we monitor."""
    DOM_MUTATIONS = auto()
    NETWORK_REQUESTS = auto()
    CSS_ANIMATIONS = auto()
    CSS_TRANSITIONS = auto()
    LAYOUT_SHIFT = auto()
    RAF_ACTIVITY = auto()


class SignalState(Enum):
    """State of an individual signal."""
    STABLE = auto()      # Signal indicates stability
    UNSTABLE = auto()    # Signal indicates instability
    UNKNOWN = auto()     # Signal not yet measured


@dataclass
class Signal:
    """
    Represents a single stability signal measurement.
    
    Attributes:
        signal_type: The type of signal
        state: Current state (stable/unstable/unknown)
        value: Raw measurement value
        threshold: Threshold used for stability decision
        is_mandatory: Whether this signal must be stable
        details: Additional diagnostic information
    """
    signal_type: SignalType
    state: SignalState
    value: Any
    threshold: Any
    is_mandatory: bool
    details: Optional[str] = None
    
    @property
    def is_stable(self) -> bool:
        return self.state == SignalState.STABLE
    
    @property
    def is_blocking(self) -> bool:
        """Returns True if this signal is blocking overall stability."""
        return self.is_mandatory and not self.is_stable


@dataclass
class StabilityStatus:
    """
    Overall stability status combining all signals.
    
    Attributes:
        is_stable: Whether UI is considered stable
        signals: Individual signal measurements
        blocking_signals: Signals preventing stability
        timestamp: When this status was measured
    """
    is_stable: bool
    signals: List[Signal]
    timestamp: float
    
    @property
    def blocking_signals(self) -> List[Signal]:
        """Get list of signals blocking stability."""
        return [s for s in self.signals if s.is_blocking]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for diagnostics."""
        return {
            'is_stable': self.is_stable,
            'timestamp': self.timestamp,
            'signals': [
                {
                    'type': s.signal_type.name,
                    'state': s.state.name,
                    'value': s.value,
                    'threshold': s.threshold,
                    'mandatory': s.is_mandatory,
                    'details': s.details,
                }
                for s in self.signals
            ],
            'blocking': [s.signal_type.name for s in self.blocking_signals],
        }


class SignalEvaluator:
    """
    Evaluates browser state against configured thresholds.
    
    This class interprets raw browser measurements and converts them
    into Signal objects with stability decisions.
    """
    
    def __init__(self, config: StabilizationConfig):
        self.config = config
    
    def evaluate(self, browser_state: Dict[str, Any], current_time: float) -> StabilityStatus:
        """
        Evaluate browser state and return stability status.
        
        Args:
            browser_state: Raw state from JavaScript instrumentation
            current_time: Current timestamp for calculations
            
        Returns:
            StabilityStatus with all signal evaluations
        """
        signals = []
        
        dom_signal = self._evaluate_dom(browser_state, current_time)
        signals.append(dom_signal)
        
        network_signal = self._evaluate_network(browser_state)
        signals.append(network_signal)
        
        if self.config.animation_detection:
            animation_signal = self._evaluate_animations(browser_state)
            signals.append(animation_signal)
        
        if self.config.strictness == 'strict' and self.config.layout_stability:
            layout_signal = self._evaluate_layout(browser_state)
            signals.append(layout_signal)
        
        is_stable = all(
            s.is_stable for s in signals if s.is_mandatory
        )
        
        if self.config.strictness == 'strict' and is_stable:
            is_stable = all(s.is_stable for s in signals)
        
        return StabilityStatus(
            is_stable=is_stable,
            signals=signals,
            timestamp=current_time,
        )
    
    def _evaluate_dom(self, state: Dict[str, Any], current_time: float) -> Signal:
        """
        Evaluate DOM mutation activity using MUTATION RATE.
        
        Key insight: Animated sites have steady ~30-50 mutations/sec (typewriter, particles).
        Loading bursts have 100+ mutations/sec. We consider stable when rate is LOW, not zero.
        
        Primary check: mutation_rate <= threshold (50/sec default)
        Fallback: time since last mutation (for older browsers)
        """
        mutation_rate = state.get('mutation_rate')
        last_mutation = state.get('last_mutation_time', 0)
        
        # Primary: Use mutation rate if available
        if mutation_rate is not None:
            threshold = self.config.mutation_rate_threshold
            is_stable = mutation_rate <= threshold
            
            details = f"Mutation rate: {mutation_rate:.0f}/sec (threshold: {threshold:.0f}/sec)"
                
            return Signal(
                signal_type=SignalType.DOM_MUTATIONS,
                state=SignalState.STABLE if is_stable else SignalState.UNSTABLE,
                value=mutation_rate,
                threshold=threshold,
                is_mandatory=True,
                details=details,
            )
        
        # Fallback: Use time since last mutation
        time_since_mutation = (current_time * 1000) - last_mutation
        threshold_ms = self.config.dom_settle_time * 1000
        is_stable = time_since_mutation >= threshold_ms
        
        return Signal(
            signal_type=SignalType.DOM_MUTATIONS,
            state=SignalState.STABLE if is_stable else SignalState.UNSTABLE,
            value=time_since_mutation,
            threshold=threshold_ms,
            is_mandatory=True,
            details=f"Last mutation {time_since_mutation:.0f}ms ago (need {threshold_ms:.0f}ms quiet)",
        )
    
    def _evaluate_network(self, state: Dict[str, Any]) -> Signal:
        """Evaluate pending network requests."""
        pending = state.get('pending_requests', 0)
        threshold = self.config.network_idle_threshold
        
        is_stable = pending <= threshold
        
        return Signal(
            signal_type=SignalType.NETWORK_REQUESTS,
            state=SignalState.STABLE if is_stable else SignalState.UNSTABLE,
            value=pending,
            threshold=threshold,
            is_mandatory=True,
            details=f"{pending} pending request(s) (threshold: {threshold})",
        )
    
    def _evaluate_animations(self, state: Dict[str, Any]) -> Signal:
        """
        Evaluate CSS animation/transition activity.
        
        Only mandatory in 'strict' mode. In 'normal' and 'relaxed' modes,
        animations are cosmetic and don't block interaction.
        """
        active = state.get('active_animations', 0)
        # Only mandatory in strict mode - animations are usually cosmetic
        is_mandatory = self.config.strictness == 'strict'
        is_stable = active == 0
        
        return Signal(
            signal_type=SignalType.CSS_ANIMATIONS,
            state=SignalState.STABLE if is_stable else SignalState.UNSTABLE,
            value=active,
            threshold=0,
            is_mandatory=is_mandatory,
            details=f"{active} active animation(s)",
        )
    
    def _evaluate_layout(self, state: Dict[str, Any]) -> Signal:
        """Evaluate layout stability (element movement)."""
        is_shifting = state.get('layout_shifting', False)
        
        return Signal(
            signal_type=SignalType.LAYOUT_SHIFT,
            state=SignalState.STABLE if not is_shifting else SignalState.UNSTABLE,
            value=is_shifting,
            threshold=False,
            is_mandatory=self.config.strictness == 'strict',
            details="Layout shifting detected" if is_shifting else "Layout stable",
        )
