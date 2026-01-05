"""
Unit tests for WebSocket and SSE tracking in instrumentation.
"""

import pytest
from waitless.instrumentation import INSTRUMENTATION_SCRIPT


class TestWebSocketTracking:
    """Tests for WebSocket interception in instrumentation script."""
    
    def test_websocket_tracking_code_present(self):
        """Test that WebSocket tracking code is in the script."""
        assert "_setupWebSocketTracking" in INSTRUMENTATION_SCRIPT
        assert "WebSocket" in INSTRUMENTATION_SCRIPT
    
    def test_websocket_state_variables(self):
        """Test that WebSocket state variables are defined."""
        assert "activeWebSockets" in INSTRUMENTATION_SCRIPT
        assert "lastWebSocketActivity" in INSTRUMENTATION_SCRIPT
        assert "webSocketDetails" in INSTRUMENTATION_SCRIPT
    
    def test_websocket_config_option(self):
        """Test that trackWebSocket config option exists."""
        assert "trackWebSocket" in INSTRUMENTATION_SCRIPT
    
    def test_websocket_events_tracked(self):
        """Test that WebSocket events are tracked."""
        assert "addEventListener" in INSTRUMENTATION_SCRIPT
        # Check for open, message, close, error events
        assert "'open'" in INSTRUMENTATION_SCRIPT
        assert "'message'" in INSTRUMENTATION_SCRIPT
        assert "'close'" in INSTRUMENTATION_SCRIPT
        assert "'error'" in INSTRUMENTATION_SCRIPT
    
    def test_websocket_prototype_preserved(self):
        """Test that WebSocket prototype is preserved."""
        assert "WebSocket.prototype" in INSTRUMENTATION_SCRIPT
        assert "WebSocket.CONNECTING" in INSTRUMENTATION_SCRIPT
        assert "WebSocket.OPEN" in INSTRUMENTATION_SCRIPT
        assert "WebSocket.CLOSED" in INSTRUMENTATION_SCRIPT
    
    def test_websocket_details_in_status(self):
        """Test that WebSocket details appear in getStatus."""
        assert "active_websockets" in INSTRUMENTATION_SCRIPT
        assert "websocket_details" in INSTRUMENTATION_SCRIPT


class TestSSETracking:
    """Tests for Server-Sent Events (EventSource) interception."""
    
    def test_sse_tracking_code_present(self):
        """Test that SSE tracking code is in the script."""
        assert "_setupSSETracking" in INSTRUMENTATION_SCRIPT
        assert "EventSource" in INSTRUMENTATION_SCRIPT
    
    def test_sse_state_variables(self):
        """Test that SSE state variables are defined."""
        assert "activeSSEConnections" in INSTRUMENTATION_SCRIPT
        assert "lastSSEActivity" in INSTRUMENTATION_SCRIPT
        assert "sseDetails" in INSTRUMENTATION_SCRIPT
    
    def test_sse_config_option(self):
        """Test that trackSSE config option exists."""
        assert "trackSSE" in INSTRUMENTATION_SCRIPT
    
    def test_sse_prototype_preserved(self):
        """Test that EventSource prototype is preserved."""
        assert "EventSource.prototype" in INSTRUMENTATION_SCRIPT
        assert "EventSource.CONNECTING" in INSTRUMENTATION_SCRIPT
        assert "EventSource.OPEN" in INSTRUMENTATION_SCRIPT
        assert "EventSource.CLOSED" in INSTRUMENTATION_SCRIPT
    
    def test_sse_details_in_status(self):
        """Test that SSE details appear in getStatus."""
        assert "active_sse" in INSTRUMENTATION_SCRIPT
        assert "sse_details" in INSTRUMENTATION_SCRIPT


class TestWebSocketSSECleanup:
    """Tests for WebSocket/SSE cleanup in destroy function."""
    
    def test_websocket_cleanup(self):
        """Test that WebSocket is restored on destroy."""
        assert "_originalWebSocket" in INSTRUMENTATION_SCRIPT
    
    def test_sse_cleanup(self):
        """Test that EventSource is restored on destroy."""
        assert "_originalEventSource" in INSTRUMENTATION_SCRIPT
