"""
Unit tests for WebSocket/SSE signal evaluation.
"""

import pytest
import time
from waitless.config import StabilizationConfig
from waitless.signals import (
    SignalEvaluator,
    SignalType,
    SignalState,
)


class TestWebSocketSignalEvaluation:
    """Tests for WebSocket signal evaluation."""
    
    @pytest.fixture
    def evaluator_with_websocket(self):
        """Create evaluator with WebSocket tracking enabled."""
        config = StabilizationConfig(track_websocket=True)
        return SignalEvaluator(config)
    
    @pytest.fixture
    def evaluator_without_websocket(self):
        """Create evaluator without WebSocket tracking."""
        config = StabilizationConfig(track_websocket=False)
        return SignalEvaluator(config)
    
    def test_websocket_signal_not_evaluated_when_disabled(self, evaluator_without_websocket):
        """Test that WebSocket signal is not evaluated when disabled."""
        browser_state = {
            'mutation_rate': 0,
            'pending_requests': 0,
        }
        
        status = evaluator_without_websocket.evaluate(browser_state, time.time())
        signal_types = [s.signal_type for s in status.signals]
        
        assert SignalType.WEBSOCKET_ACTIVITY not in signal_types
    
    def test_websocket_signal_evaluated_when_enabled(self, evaluator_with_websocket):
        """Test that WebSocket signal is evaluated when enabled."""
        browser_state = {
            'mutation_rate': 0,
            'pending_requests': 0,
            'active_websockets': 0,
            'last_websocket_activity': 0,
        }
        
        status = evaluator_with_websocket.evaluate(browser_state, time.time())
        signal_types = [s.signal_type for s in status.signals]
        
        assert SignalType.WEBSOCKET_ACTIVITY in signal_types
    
    def test_websocket_stable_when_idle(self, evaluator_with_websocket):
        """Test that idle WebSocket is considered stable."""
        current_time = time.time()
        # Activity 2 seconds ago (well past quiet time)
        old_activity = (current_time * 1000) - 2000
        
        browser_state = {
            'mutation_rate': 0,
            'pending_requests': 0,
            'active_websockets': 1,
            'last_websocket_activity': old_activity,
        }
        
        status = evaluator_with_websocket.evaluate(browser_state, current_time)
        ws_signal = next(s for s in status.signals if s.signal_type == SignalType.WEBSOCKET_ACTIVITY)
        
        assert ws_signal.state == SignalState.STABLE
    
    def test_websocket_unstable_when_recent_activity(self, evaluator_with_websocket):
        """Test that recent WebSocket activity is unstable."""
        current_time = time.time()
        # Activity 100ms ago (within quiet time of 500ms)
        recent_activity = (current_time * 1000) - 100
        
        browser_state = {
            'mutation_rate': 0,
            'pending_requests': 0,
            'active_websockets': 1,
            'last_websocket_activity': recent_activity,
        }
        
        status = evaluator_with_websocket.evaluate(browser_state, current_time)
        ws_signal = next(s for s in status.signals if s.signal_type == SignalType.WEBSOCKET_ACTIVITY)
        
        assert ws_signal.state == SignalState.UNSTABLE


class TestSSESignalEvaluation:
    """Tests for SSE signal evaluation."""
    
    @pytest.fixture
    def evaluator_with_sse(self):
        """Create evaluator with SSE tracking enabled."""
        config = StabilizationConfig(track_sse=True)
        return SignalEvaluator(config)
    
    def test_sse_signal_type_exists(self):
        """Test that SSE signal type exists."""
        assert hasattr(SignalType, 'SSE_ACTIVITY')
    
    def test_sse_signal_evaluated_when_enabled(self, evaluator_with_sse):
        """Test that SSE signal is evaluated when enabled."""
        browser_state = {
            'mutation_rate': 0,
            'pending_requests': 0,
            'active_sse': 0,
            'last_sse_activity': 0,
        }
        
        status = evaluator_with_sse.evaluate(browser_state, time.time())
        signal_types = [s.signal_type for s in status.signals]
        
        assert SignalType.SSE_ACTIVITY in signal_types
    
    def test_sse_stable_when_idle(self, evaluator_with_sse):
        """Test that idle SSE connection is considered stable."""
        current_time = time.time()
        old_activity = (current_time * 1000) - 2000
        
        browser_state = {
            'mutation_rate': 0,
            'pending_requests': 0,
            'active_sse': 1,
            'last_sse_activity': old_activity,
        }
        
        status = evaluator_with_sse.evaluate(browser_state, current_time)
        sse_signal = next(s for s in status.signals if s.signal_type == SignalType.SSE_ACTIVITY)
        
        assert sse_signal.state == SignalState.STABLE


class TestSignalTypeEnumeration:
    """Tests for SignalType enumeration."""
    
    def test_websocket_signal_type_exists(self):
        """Test WEBSOCKET_ACTIVITY signal type exists."""
        assert hasattr(SignalType, 'WEBSOCKET_ACTIVITY')
    
    def test_sse_signal_type_exists(self):
        """Test SSE_ACTIVITY signal type exists."""
        assert hasattr(SignalType, 'SSE_ACTIVITY')
    
    def test_all_signal_types_unique(self):
        """Test all signal types have unique values."""
        values = [st.value for st in SignalType]
        assert len(values) == len(set(values))
