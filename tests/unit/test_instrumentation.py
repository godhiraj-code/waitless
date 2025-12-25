"""
Unit tests for JavaScript instrumentation.
"""

import pytest
from waitless.instrumentation import (
    INSTRUMENTATION_SCRIPT,
    CHECK_ALIVE_SCRIPT,
    GET_STATUS_SCRIPT,
)


class TestInstrumentationScripts:
    """Tests for JavaScript instrumentation scripts."""
    
    def test_instrumentation_script_exists(self):
        """Test that instrumentation script is defined."""
        assert INSTRUMENTATION_SCRIPT is not None
        assert len(INSTRUMENTATION_SCRIPT) > 0
    
    def test_instrumentation_script_is_javascript(self):
        """Test that script contains JavaScript syntax."""
        # Should be a JavaScript IIFE
        assert "function" in INSTRUMENTATION_SCRIPT
        assert "window.__waitless__" in INSTRUMENTATION_SCRIPT
    
    def test_instrumentation_creates_waitless_object(self):
        """Test that script creates __waitless__ global."""
        assert "window.__waitless__" in INSTRUMENTATION_SCRIPT
        assert "_initialized" in INSTRUMENTATION_SCRIPT
    
    def test_instrumentation_has_mutation_observer(self):
        """Test that script sets up MutationObserver."""
        assert "MutationObserver" in INSTRUMENTATION_SCRIPT
    
    def test_instrumentation_has_network_tracking(self):
        """Test that script tracks network requests."""
        assert "fetch" in INSTRUMENTATION_SCRIPT
        assert "XMLHttpRequest" in INSTRUMENTATION_SCRIPT
    
    def test_instrumentation_has_animation_tracking(self):
        """Test that script tracks CSS animations."""
        assert "animationstart" in INSTRUMENTATION_SCRIPT
        assert "animationend" in INSTRUMENTATION_SCRIPT
        assert "transitionstart" in INSTRUMENTATION_SCRIPT
        assert "transitionend" in INSTRUMENTATION_SCRIPT
    
    def test_instrumentation_has_layout_tracking(self):
        """Test that script tracks layout stability."""
        assert "getBoundingClientRect" in INSTRUMENTATION_SCRIPT
    
    def test_instrumentation_prevents_reinitialization(self):
        """Test that script prevents double initialization."""
        assert "__waitless__._initialized" in INSTRUMENTATION_SCRIPT
        assert "return window.__waitless__" in INSTRUMENTATION_SCRIPT


class TestCheckAliveScript:
    """Tests for the alive-check script."""
    
    def test_check_alive_script_exists(self):
        """Test that check-alive script is defined."""
        assert CHECK_ALIVE_SCRIPT is not None
        assert len(CHECK_ALIVE_SCRIPT) > 0
    
    def test_check_alive_returns_boolean(self):
        """Test that script is designed to return a boolean."""
        # Script should call isAlive() which returns true/false
        assert "isAlive" in CHECK_ALIVE_SCRIPT or "__waitless__" in CHECK_ALIVE_SCRIPT


class TestGetStatusScript:
    """Tests for the status retrieval script."""
    
    def test_get_status_script_exists(self):
        """Test that get-status script is defined."""
        assert GET_STATUS_SCRIPT is not None
        assert len(GET_STATUS_SCRIPT) > 0
    
    def test_get_status_calls_getStatus(self):
        """Test that script calls getStatus method."""
        assert "getStatus" in GET_STATUS_SCRIPT


class TestScriptSyntax:
    """Basic syntax validation for scripts."""
    
    def test_instrumentation_script_balanced_braces(self):
        """Test that braces are balanced in instrumentation script."""
        open_braces = INSTRUMENTATION_SCRIPT.count('{')
        close_braces = INSTRUMENTATION_SCRIPT.count('}')
        assert open_braces == close_braces, f"Unbalanced braces: {open_braces} {{ vs {close_braces} }}"
    
    def test_instrumentation_script_balanced_parentheses(self):
        """Test that parentheses are balanced in instrumentation script."""
        open_parens = INSTRUMENTATION_SCRIPT.count('(')
        close_parens = INSTRUMENTATION_SCRIPT.count(')')
        assert open_parens == close_parens, f"Unbalanced parens: {open_parens} ( vs {close_parens} )"
    
    def test_instrumentation_script_balanced_brackets(self):
        """Test that brackets are balanced in instrumentation script."""
        open_brackets = INSTRUMENTATION_SCRIPT.count('[')
        close_brackets = INSTRUMENTATION_SCRIPT.count(']')
        assert open_brackets == close_brackets, f"Unbalanced brackets: {open_brackets} [ vs {close_brackets} ]"
