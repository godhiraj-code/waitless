"""
Unit tests for iframe tracking in instrumentation.
"""

import pytest
from waitless.instrumentation import INSTRUMENTATION_SCRIPT


class TestIframeTracking:
    """Tests for iframe instrumentation injection."""
    
    def test_iframe_tracking_code_present(self):
        """Test that iframe tracking code is in the script."""
        assert "_setupIframeTracking" in INSTRUMENTATION_SCRIPT
        assert "_injectIntoIframe" in INSTRUMENTATION_SCRIPT
    
    def test_iframe_state_variables(self):
        """Test that iframe state variables are defined."""
        assert "iframeStatus" in INSTRUMENTATION_SCRIPT
    
    def test_iframe_config_option(self):
        """Test that trackIframes config option exists."""
        assert "trackIframes" in INSTRUMENTATION_SCRIPT
    
    def test_iframe_observer_setup(self):
        """Test that iframe MutationObserver is set up."""
        # Script should observe for new iframes
        assert "IFRAME" in INSTRUMENTATION_SCRIPT
    
    def test_iframe_queryselector(self):
        """Test that existing iframes are queried."""
        assert "querySelectorAll" in INSTRUMENTATION_SCRIPT
        assert "'iframe'" in INSTRUMENTATION_SCRIPT
    
    def test_iframe_cross_origin_handling(self):
        """Test that cross-origin iframes are handled gracefully."""
        assert "cross-origin" in INSTRUMENTATION_SCRIPT
    
    def test_iframe_load_event(self):
        """Test that iframe load events are tracked."""
        assert "'load'" in INSTRUMENTATION_SCRIPT
    
    def test_iframe_content_access(self):
        """Test that script tries to access iframe content."""
        assert "contentDocument" in INSTRUMENTATION_SCRIPT
        assert "contentWindow" in INSTRUMENTATION_SCRIPT
