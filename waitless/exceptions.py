"""
Waitless custom exceptions.

Provides clear, actionable error types for stability-related failures.
"""

from typing import Optional, Dict, Any


class WaitlessError(Exception):
    """Base exception for all waitless errors."""
    pass


class StabilizationTimeout(WaitlessError):
    """
    Raised when UI doesn't stabilize within the configured timeout.
    
    Contains diagnostic information about what was blocking stability.
    """
    
    def __init__(
        self,
        message: str,
        timeout: float,
        blocking_factors: Optional[Dict[str, Any]] = None,
        timeline: Optional[list] = None
    ):
        super().__init__(message)
        self.timeout = timeout
        self.blocking_factors = blocking_factors or {}
        self.timeline = timeline or []
    
    def get_diagnostic_summary(self) -> str:
        """Return a human-readable summary of what blocked stability."""
        lines = [
            f"\n{'='*60}",
            "STABILIZATION TIMEOUT - UI did not become stable",
            f"{'='*60}",
            f"Timeout: {self.timeout}s",
            "",
            "BLOCKING FACTORS:",
        ]
        
        if not self.blocking_factors:
            lines.append("  (No specific blocking factors captured)")
        else:
            if self.blocking_factors.get('pending_requests', 0) > 0:
                count = self.blocking_factors['pending_requests']
                lines.append(f"  ⚠ NETWORK: {count} request(s) still pending")
                
            if self.blocking_factors.get('recent_mutations', 0) > 0:
                count = self.blocking_factors['recent_mutations']
                lines.append(f"  ⚠ DOM: {count} mutation(s) in last interval")
                
            if self.blocking_factors.get('active_animations', 0) > 0:
                count = self.blocking_factors['active_animations']
                lines.append(f"  ⚠ ANIMATIONS: {count} active animation(s)")
                
            if self.blocking_factors.get('layout_shifting'):
                lines.append("  ⚠ LAYOUT: Elements still moving")
        
        lines.extend([
            "",
            "SUGGESTIONS:",
            "  1. Increase timeout if slow network is expected",
            "  2. Set network_idle_threshold > 0 if background requests exist",
            "  3. Use strictness='relaxed' to ignore animations",
            "  4. Run 'waitless doctor' for detailed diagnostics",
            f"{'='*60}",
        ])
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        base = super().__str__()
        return f"{base}\n{self.get_diagnostic_summary()}"


class InstrumentationError(WaitlessError):
    """
    Raised when JavaScript instrumentation fails to inject or execute.
    
    This usually indicates:
    - Page navigation occurred and destroyed the instrumentation
    - JavaScript is disabled
    - CSP policy blocking script execution
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class ConfigurationError(WaitlessError):
    """
    Raised when invalid configuration is provided.
    """
    pass


class NotStabilizedError(WaitlessError):
    """
    Raised when an interaction is attempted without stabilization.
    
    This is only raised in strict mode when auto-stabilization is disabled.
    """
    pass
