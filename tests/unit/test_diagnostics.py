"""
Unit tests for diagnostics module.
"""

import pytest
import json
from waitless.diagnostics import DiagnosticReport, generate_report, print_report


class TestDiagnosticReport:
    """Tests for DiagnosticReport class."""
    
    def test_basic_creation(self):
        """Test creating a diagnostic report."""
        diagnostics = {
            'config': {
                'timeout': 10,
                'strictness': 'normal',
                'network_idle_threshold': 2,
                'animation_detection': True,
            },
            'blocking_factors': {},
            'timeline': [],
        }
        
        report = DiagnosticReport(diagnostics)
        
        assert report.diagnostics == diagnostics
        assert report.timestamp is not None
    
    def test_generate_text_report_includes_header(self):
        """Test that text report includes header."""
        diagnostics = {
            'config': {
                'timeout': 10,
                'strictness': 'normal',
            },
            'blocking_factors': {},
        }
        
        report = DiagnosticReport(diagnostics)
        text = report.generate_text_report()
        
        assert "WAITLESS STABILITY REPORT" in text
    
    def test_generate_text_report_includes_config(self):
        """Test that text report includes configuration."""
        diagnostics = {
            'config': {
                'timeout': 15,
                'strictness': 'strict',
                'network_idle_threshold': 0,
                'animation_detection': True,
            },
            'blocking_factors': {},
        }
        
        report = DiagnosticReport(diagnostics)
        text = report.generate_text_report()
        
        assert "Timeout: 15s" in text
        assert "Strictness: strict" in text
    
    def test_generates_network_blocking_suggestion(self):
        """Test suggestions when network requests are blocking."""
        diagnostics = {
            'config': {
                'timeout': 10,
                'strictness': 'normal',
                'network_idle_threshold': 0,
            },
            'blocking_factors': {
                'pending_requests': 3,
                'pending_request_details': [],
            },
        }
        
        report = DiagnosticReport(diagnostics)
        text = report.generate_text_report()
        
        assert "NETWORK" in text
        assert "3 request(s)" in text
        assert "SUGGESTIONS" in text
    
    def test_generates_animation_blocking_suggestion(self):
        """Test suggestions when animations are blocking."""
        diagnostics = {
            'config': {
                'timeout': 10,
                'strictness': 'strict',
            },
            'blocking_factors': {
                'active_animations': 2,
            },
        }
        
        report = DiagnosticReport(diagnostics)
        text = report.generate_text_report()
        
        assert "ANIMATIONS" in text
        assert "2 active animation(s)" in text
    
    def test_generates_layout_blocking_suggestion(self):
        """Test suggestions when layout is shifting."""
        diagnostics = {
            'config': {
                'timeout': 10,
            },
            'blocking_factors': {
                'layout_shifting': True,
            },
        }
        
        report = DiagnosticReport(diagnostics)
        text = report.generate_text_report()
        
        assert "LAYOUT" in text
        assert "Elements" in text
    
    def test_to_json_valid_format(self):
        """Test JSON export is valid."""
        diagnostics = {
            'config': {'timeout': 10},
            'blocking_factors': {},
        }
        
        report = DiagnosticReport(diagnostics)
        json_str = report.to_json()
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        
        assert 'timestamp' in parsed
        assert 'diagnostics' in parsed
        assert parsed['diagnostics']['config']['timeout'] == 10
    
    def test_timeline_display_limited(self):
        """Test that only recent timeline events are shown."""
        timeline = [{'time': i, 'message': f'Event {i}'} for i in range(20)]
        
        diagnostics = {
            'config': {'timeout': 10},
            'blocking_factors': {},
            'timeline': timeline,
        }
        
        report = DiagnosticReport(diagnostics)
        text = report.generate_text_report()
        
        # Should only show last 10 events
        assert "RECENT EVENTS (last 10)" in text

    def test_engine_diagnostics_redact_url_queries_and_fragments(self):
        from waitless.engine import StabilizationEngine

        engine = StabilizationEngine(driver=object())
        engine._last_browser_state = {
            'pending_request_details': [
                {'url': 'https://user:secret@example.test/api?token=secret#fragment', 'type': 'fetch'}
            ],
            'websocket_details': [
                {'url': 'wss://user:secret@example.test/socket?access_token=secret', 'state': 'open'}
            ],
            'sse_details': [
                {'url': 'https://user:secret@example.test/events?token=secret', 'state': 'open'}
            ],
            'iframe_status': [
                {'src': 'https://user:secret@example.test/frame?token=secret', 'loaded': True}
            ],
            'timeline': [
                {
                    'message': 'Request started',
                    'data': {'url': 'https://user:secret@example.test/data?email=user@example.test'},
                }
            ],
        }

        diagnostics = engine.get_diagnostics()

        assert diagnostics['browser_state']['pending_request_details'][0]['url'] == 'https://example.test/api'
        assert diagnostics['browser_state']['websocket_details'][0]['url'] == 'wss://example.test/socket'
        assert diagnostics['browser_state']['sse_details'][0]['url'] == 'https://example.test/events'
        assert diagnostics['browser_state']['iframe_status'][0]['src'] == 'https://example.test/frame'
        assert diagnostics['browser_state']['timeline'][0]['data']['url'] == 'https://example.test/data'


class TestHelperFunctions:
    """Test module-level helper functions."""
    
    def test_generate_report_returns_diagnostic_report(self):
        """Test generate_report returns a DiagnosticReport."""
        # Create a mock engine with get_diagnostics method
        class MockEngine:
            def get_diagnostics(self):
                return {
                    'config': {'timeout': 5},
                    'blocking_factors': {},
                }
        
        report = generate_report(MockEngine())
        
        assert isinstance(report, DiagnosticReport)
    
    def test_print_report_outputs_text(self, capsys):
        """Test print_report outputs to stdout."""
        class MockEngine:
            def get_diagnostics(self):
                return {
                    'config': {'timeout': 5},
                    'blocking_factors': {},
                }
        
        print_report(MockEngine())
        
        captured = capsys.readouterr()
        assert "WAITLESS STABILITY REPORT" in captured.out
