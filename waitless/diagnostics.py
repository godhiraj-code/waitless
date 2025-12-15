"""
Diagnostics and doctor feature.

Provides detailed analysis of stability issues with actionable suggestions.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import StabilizationEngine


class DiagnosticReport:
    """
    Generates human-readable diagnostic reports for stability issues.
    """
    
    def __init__(self, diagnostics: Dict[str, Any]):
        self.diagnostics = diagnostics
        self.timestamp = datetime.now()
    
    def generate_text_report(self) -> str:
        """Generate a text-based diagnostic report."""
        lines = []
        lines.append("╔" + "═" * 66 + "╗")
        lines.append("║" + "WAITLESS STABILITY REPORT".center(66) + "║")
        lines.append("╠" + "═" * 66 + "╣")
        lines.append(f"║ Report generated at: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S'):<43} ║")
        
        config = self.diagnostics.get('config', {})
        lines.append("╠" + "═" * 66 + "╣")
        lines.append("║ CONFIGURATION:".ljust(67) + "║")
        lines.append(f"║   Timeout: {config.get('timeout', 'N/A')}s".ljust(67) + "║")
        lines.append(f"║   Strictness: {config.get('strictness', 'N/A')}".ljust(67) + "║")
        lines.append(f"║   Network threshold: {config.get('network_idle_threshold', 'N/A')} pending requests".ljust(67) + "║")
        lines.append(f"║   Animation detection: {config.get('animation_detection', 'N/A')}".ljust(67) + "║")
        
        blocking = self.diagnostics.get('blocking_factors', {})
        if blocking:
            lines.append("╠" + "═" * 66 + "╣")
            lines.append("║ BLOCKING FACTORS:".ljust(67) + "║")
            lines.append("║".ljust(67) + "║")
            
            pending = blocking.get('pending_requests', 0)
            if pending > 0:
                lines.append("║ ⚠ NETWORK: {} request(s) still pending".format(pending).ljust(67) + "║")
                
                details = blocking.get('pending_request_details', [])
                for req in details[:5]:  # Show max 5
                    url = req.get('url', 'unknown')[:50]
                    started = req.get('startTime', 0)
                    lines.append(f"║   → {req.get('type', 'unknown').upper()} {url}".ljust(67) + "║")
                
                if len(details) > 5:
                    lines.append(f"║   ... and {len(details) - 5} more".ljust(67) + "║")
                lines.append("║".ljust(67) + "║")
            
            animations = blocking.get('active_animations', 0)
            if animations > 0:
                lines.append(f"║ ⚠ ANIMATIONS: {animations} active animation(s)".ljust(67) + "║")
                lines.append("║".ljust(67) + "║")
            
            if blocking.get('layout_shifting'):
                lines.append("║ ⚠ LAYOUT: Elements are still moving".ljust(67) + "║")
                lines.append("║".ljust(67) + "║")
        
        status = self.diagnostics.get('last_status')
        if status:
            lines.append("╠" + "═" * 66 + "╣")
            lines.append("║ SIGNAL STATUS:".ljust(67) + "║")
            
            for signal in status.get('signals', []):
                state = "✓" if signal['state'] == 'STABLE' else "✗"
                mandatory = "[M]" if signal['mandatory'] else "[O]"
                line = f"║   {state} {mandatory} {signal['type']}: {signal.get('details', 'N/A')}"
                lines.append(line[:66].ljust(67) + "║")
        
        timeline = self.diagnostics.get('timeline', [])
        if timeline:
            lines.append("╠" + "═" * 66 + "╣")
            lines.append("║ RECENT EVENTS (last 10):".ljust(67) + "║")
            
            for entry in timeline[-10:]:
                time_str = str(entry.get('time', ''))[-6:]
                msg = entry.get('message', '')[:50]
                lines.append(f"║   [{time_str}] {msg}".ljust(67) + "║")
        
        lines.extend(self._generate_suggestions())
        lines.append("╚" + "═" * 66 + "╝")
        
        return "\n".join(lines)
    
    def _generate_suggestions(self) -> List[str]:
        """Generate actionable suggestions based on diagnostics."""
        lines = []
        suggestions = []
        
        blocking = self.diagnostics.get('blocking_factors', {})
        config = self.diagnostics.get('config', {})
        pending = blocking.get('pending_requests', 0)
        if pending > 0:
            threshold = config.get('network_idle_threshold', 0)
            if threshold == 0:
                suggestions.append(
                    "Network requests are blocking stability. If your app has "
                    "background traffic (analytics, polling), consider:\n"
                    "     config = StabilizationConfig(network_idle_threshold=2)"
                )
            
            details = blocking.get('pending_request_details', [])
            slow_apis = [r for r in details if '/api/' in r.get('url', '')]
            if slow_apis:
                suggestions.append(
                    "Slow API endpoints detected. Consider:\n"
                    "     - Mocking slow endpoints in tests\n"
                    "     - Increasing timeout if APIs are legitimately slow"
                )
        animations = blocking.get('active_animations', 0)
        if animations > 0:
            suggestions.append(
                "CSS animations are blocking stability. If you have infinite "
                "animations (spinners), consider:\n"
                "     config = StabilizationConfig(animation_detection=False)\n"
                "     OR use strictness='relaxed'"
            )
        if blocking.get('layout_shifting'):
            suggestions.append(
                "Layout is unstable (elements moving). This often indicates:\n"
                "     - Images loading without dimensions\n"
                "     - Font loading causing reflow\n"
                "     - Dynamic content insertion"
            )
        timeout = config.get('timeout', 10)
        if timeout >= 10:
            suggestions.append(
                f"Timeout is {timeout}s (default). For faster feedback, consider:\n"
                "     config = StabilizationConfig(timeout=5)"
            )
        
        if suggestions:
            lines.append("╠" + "═" * 66 + "╣")
            lines.append("║ SUGGESTIONS:".ljust(67) + "║")
            lines.append("║".ljust(67) + "║")
            
            for i, suggestion in enumerate(suggestions, 1):
                for line in f"{i}. {suggestion}".split('\n'):
                    lines.append(f"║ {line}".ljust(67) + "║")
                lines.append("║".ljust(67) + "║")
        
        return lines
    
    def to_json(self) -> str:
        """Export diagnostics as JSON for CI integration."""
        return json.dumps({
            'timestamp': self.timestamp.isoformat(),
            'diagnostics': self.diagnostics,
        }, indent=2, default=str)


def generate_report(engine: 'StabilizationEngine') -> DiagnosticReport:
    """Generate a diagnostic report from an engine."""
    diagnostics = engine.get_diagnostics()
    return DiagnosticReport(diagnostics)


def print_report(engine: 'StabilizationEngine') -> None:
    """Print a diagnostic report to stdout."""
    report = generate_report(engine)
    print(report.generate_text_report())
