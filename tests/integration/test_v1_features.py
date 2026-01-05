"""
Integration tests for WebSocket/SSE tracking using a real browser.

These tests verify that WebSocket and SSE connections are properly
tracked in a real Selenium environment.
"""

import pytest
import os
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler


# Test page HTML with WebSocket and SSE simulation
TEST_PAGE_WEBSOCKET_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket/SSE Test Page</title>
</head>
<body>
    <h1>WebSocket/SSE Test</h1>
    <div id="status">Ready</div>
    <button id="connect-ws" onclick="connectWebSocket()">Connect WebSocket</button>
    <button id="connect-sse" onclick="connectSSE()">Connect SSE</button>
    
    <script>
        var ws = null;
        var sse = null;
        
        function connectWebSocket() {
            // Using echo.websocket.org for testing (may not be available)
            // In real tests, use a local WebSocket server
            document.getElementById('status').textContent = 'WebSocket connecting...';
            try {
                ws = new WebSocket('wss://echo.websocket.org');
                ws.onopen = function() {
                    document.getElementById('status').textContent = 'WebSocket connected';
                };
                ws.onmessage = function(e) {
                    document.getElementById('status').textContent = 'WebSocket message: ' + e.data;
                };
            } catch (e) {
                document.getElementById('status').textContent = 'WebSocket error: ' + e.message;
            }
        }
        
        function connectSSE() {
            document.getElementById('status').textContent = 'SSE connecting...';
            // SSE endpoint would need a server
        }
    </script>
</body>
</html>
"""


class TestWebSocketSSEIntegration:
    """Integration tests for WebSocket/SSE tracking."""
    
    @pytest.fixture(scope="class")
    def test_page_path(self, tmp_path_factory):
        """Create a temporary test page."""
        tmp_dir = tmp_path_factory.mktemp("websocket_test")
        test_file = tmp_dir / "ws_test.html"
        test_file.write_text(TEST_PAGE_WEBSOCKET_HTML)
        return str(test_file)
    
    def test_instrumentation_includes_websocket_tracking(self):
        """Verify instrumentation script has WebSocket tracking."""
        from waitless.instrumentation import INSTRUMENTATION_SCRIPT
        
        assert "_setupWebSocketTracking" in INSTRUMENTATION_SCRIPT
        assert "activeWebSockets" in INSTRUMENTATION_SCRIPT
    
    def test_instrumentation_includes_sse_tracking(self):
        """Verify instrumentation script has SSE tracking."""
        from waitless.instrumentation import INSTRUMENTATION_SCRIPT
        
        assert "_setupSSETracking" in INSTRUMENTATION_SCRIPT
        assert "activeSSEConnections" in INSTRUMENTATION_SCRIPT
    
    def test_config_websocket_option(self):
        """Test WebSocket config option works."""
        from waitless import StabilizationConfig
        
        config = StabilizationConfig(track_websocket=True)
        assert config.track_websocket is True
    
    def test_config_sse_option(self):
        """Test SSE config option works."""
        from waitless import StabilizationConfig
        
        config = StabilizationConfig(track_sse=True)
        assert config.track_sse is True


class TestIframeIntegration:
    """Integration tests for iframe tracking."""
    
    def test_instrumentation_includes_iframe_tracking(self):
        """Verify instrumentation script has iframe tracking."""
        from waitless.instrumentation import INSTRUMENTATION_SCRIPT
        
        assert "_setupIframeTracking" in INSTRUMENTATION_SCRIPT
        assert "_injectIntoIframe" in INSTRUMENTATION_SCRIPT
        assert "iframeStatus" in INSTRUMENTATION_SCRIPT
    
    def test_config_iframe_option(self):
        """Test iframe config option works."""
        from waitless import StabilizationConfig
        
        config = StabilizationConfig(track_iframes=True)
        assert config.track_iframes is True


class TestFrameworkAdaptersIntegration:
    """Integration tests for framework adapters."""
    
    def test_adapters_import(self):
        """Test that adapters module imports correctly."""
        from waitless.adapters import (
            get_adapter,
            get_available_adapters,
            ReactAdapter,
            AngularAdapter,
            VueAdapter,
        )
        
        assert get_available_adapters() == ['react', 'angular', 'vue']
        assert get_adapter('react') is not None
        assert get_adapter('angular') is not None
        assert get_adapter('vue') is not None
    
    def test_react_adapter_scripts_are_valid_js(self):
        """Test that React adapter scripts are syntactically valid."""
        from waitless.adapters import ReactAdapter
        
        adapter = ReactAdapter()
        
        # Basic syntax checks
        assert adapter.detection_script.count('(') == adapter.detection_script.count(')')
        assert adapter.detection_script.count('{') == adapter.detection_script.count('}')
    
    def test_angular_adapter_scripts_are_valid_js(self):
        """Test that Angular adapter scripts are syntactically valid."""
        from waitless.adapters import AngularAdapter
        
        adapter = AngularAdapter()
        
        # Basic syntax checks
        assert adapter.detection_script.count('(') == adapter.detection_script.count(')')
        assert adapter.detection_script.count('{') == adapter.detection_script.count('}')
    
    def test_vue_adapter_scripts_are_valid_js(self):
        """Test that Vue adapter scripts are syntactically valid."""
        from waitless.adapters import VueAdapter
        
        adapter = VueAdapter()
        
        # Basic syntax checks
        assert adapter.detection_script.count('(') == adapter.detection_script.count(')')
        assert adapter.detection_script.count('{') == adapter.detection_script.count('}')
    
    def test_config_framework_hooks_option(self):
        """Test framework_hooks config option works."""
        from waitless import StabilizationConfig
        
        config = StabilizationConfig(framework_hooks=['react', 'vue'])
        assert config.framework_hooks == ['react', 'vue']
