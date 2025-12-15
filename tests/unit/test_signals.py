"""
Unit tests for stability signals.
"""

import pytest
import time
from waitless.signals import (
    SignalType,
    SignalState,
    Signal,
    StabilityStatus,
    SignalEvaluator,
)
from waitless.config import StabilizationConfig


class TestSignal:
    """Tests for Signal dataclass."""
    
    def test_stable_signal(self):
        """Test stable signal properties."""
        signal = Signal(
            signal_type=SignalType.NETWORK_REQUESTS,
            state=SignalState.STABLE,
            value=0,
            threshold=0,
            is_mandatory=True,
        )
        
        assert signal.is_stable is True
        assert signal.is_blocking is False
    
    def test_unstable_mandatory_signal(self):
        """Test unstable mandatory signal blocks."""
        signal = Signal(
            signal_type=SignalType.NETWORK_REQUESTS,
            state=SignalState.UNSTABLE,
            value=3,
            threshold=0,
            is_mandatory=True,
        )
        
        assert signal.is_stable is False
        assert signal.is_blocking is True
    
    def test_unstable_optional_signal(self):
        """Test unstable optional signal doesn't block."""
        signal = Signal(
            signal_type=SignalType.CSS_ANIMATIONS,
            state=SignalState.UNSTABLE,
            value=1,
            threshold=0,
            is_mandatory=False,
        )
        
        assert signal.is_stable is False
        assert signal.is_blocking is False


class TestStabilityStatus:
    """Tests for StabilityStatus."""
    
    def test_blocking_signals(self):
        """Test blocking_signals property."""
        signals = [
            Signal(SignalType.DOM_MUTATIONS, SignalState.STABLE, 0, 0, True),
            Signal(SignalType.NETWORK_REQUESTS, SignalState.UNSTABLE, 2, 0, True),
            Signal(SignalType.CSS_ANIMATIONS, SignalState.UNSTABLE, 1, 0, False),
        ]
        
        status = StabilityStatus(
            is_stable=False,
            signals=signals,
            timestamp=time.time(),
        )
        
        blocking = status.blocking_signals
        assert len(blocking) == 1
        assert blocking[0].signal_type == SignalType.NETWORK_REQUESTS
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        status = StabilityStatus(
            is_stable=True,
            signals=[
                Signal(SignalType.DOM_MUTATIONS, SignalState.STABLE, 0, 0, True),
            ],
            timestamp=12345.0,
        )
        
        d = status.to_dict()
        
        assert d['is_stable'] is True
        assert d['timestamp'] == 12345.0
        assert len(d['signals']) == 1
        assert d['blocking'] == []


class TestSignalEvaluator:
    """Tests for SignalEvaluator."""
    
    def test_evaluate_stable(self):
        """Test evaluation when all signals are stable."""
        config = StabilizationConfig(network_idle_threshold=0)
        evaluator = SignalEvaluator(config)
        
        browser_state = {
            'pending_requests': 0,
            'last_mutation_time': time.time() * 1000 - 200,  # 200ms ago
            'active_animations': 0,
            'layout_shifting': False,
        }
        
        status = evaluator.evaluate(browser_state, time.time())
        
        assert status.is_stable is True
        assert len(status.blocking_signals) == 0
    
    def test_evaluate_pending_requests(self):
        """Test evaluation with pending requests."""
        config = StabilizationConfig(network_idle_threshold=0)
        evaluator = SignalEvaluator(config)
        
        browser_state = {
            'pending_requests': 2,
            'last_mutation_time': time.time() * 1000 - 200,
            'active_animations': 0,
        }
        
        status = evaluator.evaluate(browser_state, time.time())
        
        assert status.is_stable is False
        blocking = [s.signal_type for s in status.blocking_signals]
        assert SignalType.NETWORK_REQUESTS in blocking
    
    def test_evaluate_recent_mutation(self):
        """Test evaluation with recent DOM mutation."""
        config = StabilizationConfig(dom_settle_time=0.1)
        evaluator = SignalEvaluator(config)
        
        browser_state = {
            'pending_requests': 0,
            'last_mutation_time': time.time() * 1000 - 50,  # 50ms ago
            'active_animations': 0,
        }
        
        status = evaluator.evaluate(browser_state, time.time())
        
        assert status.is_stable is False
        blocking = [s.signal_type for s in status.blocking_signals]
        assert SignalType.DOM_MUTATIONS in blocking
    
    def test_network_threshold_allows_pending(self):
        """Test that network threshold allows some pending requests."""
        config = StabilizationConfig(network_idle_threshold=2)
        evaluator = SignalEvaluator(config)
        
        browser_state = {
            'pending_requests': 2,
            'last_mutation_time': time.time() * 1000 - 200,
            'active_animations': 0,
        }
        
        status = evaluator.evaluate(browser_state, time.time())
        
        # Should be stable because 2 <= threshold of 2
        assert status.is_stable is True
    
    def test_relaxed_mode_ignores_animations(self):
        """Test relaxed mode doesn't wait for animations."""
        config = StabilizationConfig(strictness='relaxed')
        evaluator = SignalEvaluator(config)
        
        browser_state = {
            'pending_requests': 0,
            'last_mutation_time': time.time() * 1000 - 200,
            'active_animations': 5,  # Many animations
        }
        
        status = evaluator.evaluate(browser_state, time.time())
        
        # Should be stable in relaxed mode despite animations
        assert status.is_stable is True
    
    def test_strict_mode_requires_all_stable(self):
        """Test strict mode requires all signals stable."""
        config = StabilizationConfig(strictness='strict')
        evaluator = SignalEvaluator(config)
        
        browser_state = {
            'pending_requests': 0,
            'last_mutation_time': time.time() * 1000 - 200,
            'active_animations': 1,  # One animation
            'layout_shifting': False,
        }
        
        status = evaluator.evaluate(browser_state, time.time())
        
        # Should be unstable in strict mode due to animation
        assert status.is_stable is False
