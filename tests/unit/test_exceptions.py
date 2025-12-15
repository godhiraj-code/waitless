"""
Unit tests for exceptions.
"""

import pytest
from waitless.exceptions import (
    WaitlessError,
    StabilizationTimeout,
    InstrumentationError,
    ConfigurationError,
    NotStabilizedError,
)


class TestStabilizationTimeout:
    """Tests for StabilizationTimeout exception."""
    
    def test_basic_creation(self):
        """Test basic exception creation."""
        exc = StabilizationTimeout(
            message="UI did not stabilize",
            timeout=10.0,
        )
        
        assert exc.timeout == 10.0
        assert exc.blocking_factors == {}
        assert exc.timeline == []
    
    def test_with_blocking_factors(self):
        """Test exception with blocking factors."""
        exc = StabilizationTimeout(
            message="Timeout",
            timeout=5.0,
            blocking_factors={
                'pending_requests': 3,
                'active_animations': 1,
            }
        )
        
        assert exc.blocking_factors['pending_requests'] == 3
        assert exc.blocking_factors['active_animations'] == 1
    
    def test_diagnostic_summary_with_network(self):
        """Test diagnostic summary includes network info."""
        exc = StabilizationTimeout(
            message="Timeout",
            timeout=10.0,
            blocking_factors={'pending_requests': 2},
        )
        
        summary = exc.get_diagnostic_summary()
        
        assert "NETWORK" in summary
        assert "2 request(s)" in summary
    
    def test_diagnostic_summary_with_animations(self):
        """Test diagnostic summary includes animation info."""
        exc = StabilizationTimeout(
            message="Timeout",
            timeout=10.0,
            blocking_factors={'active_animations': 3},
        )
        
        summary = exc.get_diagnostic_summary()
        
        assert "ANIMATIONS" in summary
        assert "3 active" in summary
    
    def test_str_includes_diagnostics(self):
        """Test __str__ includes diagnostic information."""
        exc = StabilizationTimeout(
            message="UI timeout",
            timeout=10.0,
            blocking_factors={'pending_requests': 1},
        )
        
        string = str(exc)
        
        assert "UI timeout" in string
        assert "STABILIZATION TIMEOUT" in string
        assert "SUGGESTIONS" in string


class TestInstrumentationError:
    """Tests for InstrumentationError."""
    
    def test_with_original_error(self):
        """Test preserving original error."""
        original = ValueError("JavaScript error")
        exc = InstrumentationError(
            message="Failed to inject",
            original_error=original,
        )
        
        assert exc.original_error is original
        assert "Failed to inject" in str(exc)


class TestExceptionHierarchy:
    """Test exception inheritance."""
    
    def test_all_inherit_from_base(self):
        """Test all exceptions inherit from WaitlessError."""
        assert issubclass(StabilizationTimeout, WaitlessError)
        assert issubclass(InstrumentationError, WaitlessError)
        assert issubclass(ConfigurationError, WaitlessError)
        assert issubclass(NotStabilizedError, WaitlessError)
    
    def test_base_inherits_from_exception(self):
        """Test base inherits from Exception."""
        assert issubclass(WaitlessError, Exception)
