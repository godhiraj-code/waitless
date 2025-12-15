"""
Core stabilization engine.

This is the heart of waitless - it manages JavaScript injection,
polls for stability status, and makes the final stability decision.
"""

import time
import threading
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING

from .config import StabilizationConfig, DEFAULT_CONFIG
from .signals import SignalEvaluator, StabilityStatus
from .instrumentation import (
    INSTRUMENTATION_SCRIPT,
    CHECK_ALIVE_SCRIPT,
    GET_STATUS_SCRIPT,
)
from .exceptions import StabilizationTimeout, InstrumentationError


if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


logger = logging.getLogger('waitless')


class StabilizationEngine:
    """
    Core engine that manages stability detection for a WebDriver instance.
    
    Thread-safe: Uses locks to prevent concurrent stabilization calls.
    
    Usage:
        engine = StabilizationEngine(driver, config)
        engine.wait_for_stability()
    """
    
    def __init__(
        self,
        driver: 'WebDriver',
        config: Optional[StabilizationConfig] = None
    ):
        self.driver = driver
        self.config = config or DEFAULT_CONFIG
        self.evaluator = SignalEvaluator(self.config)
        
        self._lock = threading.Lock()
        self._instrumented = False
        self._last_url: Optional[str] = None
        

        self._last_status: Optional[StabilityStatus] = None
        self._last_browser_state: Optional[Dict[str, Any]] = None
        self._last_blocking_factors: Dict[str, Any] = {}
        self._timeline: list = []
        
        if self.config.debug_mode:
            logging.basicConfig(level=logging.DEBUG)
            logger.setLevel(logging.DEBUG)
    
    def ensure_instrumented(self) -> None:
        """
        Ensure JavaScript instrumentation is active in the browser.
        
        Re-injects if:
        - Never injected before
        - Page navigated (URL changed)
        - Instrumentation is not responding
        """
        current_url = self._get_current_url()
        
        needs_injection = (
            not self._instrumented or
            current_url != self._last_url or
            not self._is_instrumentation_alive()
        )
        
        if needs_injection:
            self._inject_instrumentation()
            self._last_url = current_url
    
    def _get_current_url(self) -> str:
        """Get current page URL safely."""
        try:
            return self.driver.current_url
        except Exception:
            return ""
    
    def _is_instrumentation_alive(self) -> bool:
        """
        Check if the __waitless__ object is still alive and wired.
        
        This is the re-validation check mentioned in architecture:
        Before every stabilization call, verify instrumentation is active.
        """
        try:
            result = self.driver.execute_script(CHECK_ALIVE_SCRIPT)
            return result is True
        except Exception:
            return False
    
    def _inject_instrumentation(self) -> None:
        """Inject JavaScript instrumentation into the page."""
        try:
            self.driver.execute_script(INSTRUMENTATION_SCRIPT)
            self._instrumented = True
            self._debug("Instrumentation injected successfully")
        except Exception as e:
            self._instrumented = False
            raise InstrumentationError(
                f"Failed to inject instrumentation: {e}",
                original_error=e
            )
    
    def _get_browser_status(self) -> Optional[Dict[str, Any]]:
        """Get current stability status from browser."""
        try:
            return self.driver.execute_script(GET_STATUS_SCRIPT)
        except Exception as e:
            self._debug(f"Failed to get browser status: {e}")
            return None
    
    def wait_for_stability(self, timeout: Optional[float] = None) -> StabilityStatus:
        """
        Wait for UI to become stable.
        
        This is the main entry point for stability waiting.
        Thread-safe.
        
        Args:
            timeout: Override default timeout (seconds)
            
        Returns:
            StabilityStatus when stable
            
        Raises:
            StabilizationTimeout: If UI doesn't stabilize in time
            InstrumentationError: If JavaScript injection fails
        """
        with self._lock:
            return self._wait_for_stability_impl(timeout)
    
    def _wait_for_stability_impl(self, timeout: Optional[float] = None) -> StabilityStatus:
        """Internal implementation of stability waiting."""
        effective_timeout = timeout or self.config.timeout
        start_time = time.time()
        
        self.ensure_instrumented()
        
        last_status: Optional[StabilityStatus] = None
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed >= effective_timeout:
                # Timeout - collect diagnostic info and raise
                self._handle_timeout(effective_timeout, last_status)
            
            browser_state = self._get_browser_status()
            
            if browser_state is None:
                if self.config.reinject_on_navigation:
                    self._debug("Browser status unavailable, attempting reinject")
                    self._inject_instrumentation()
                    time.sleep(self.config.poll_interval)
                    continue
                else:
                    raise InstrumentationError(
                        "Lost connection to browser instrumentation"
                    )
            
            current_time = time.time()
            status = self.evaluator.evaluate(browser_state, current_time)
            last_status = status
            self._last_status = status
            self._last_browser_state = browser_state  # Store for diagnostics
            
            if status.is_stable:
                self._debug(f"UI stable after {elapsed:.2f}s")
                return status
            
            self._update_diagnostics(browser_state, status)
            time.sleep(self.config.poll_interval)
    
    def _handle_timeout(
        self,
        timeout: float,
        last_status: Optional[StabilityStatus]
    ) -> None:
        """Handle stabilization timeout with detailed diagnostics."""
        blocking_factors = {}
        
        if last_status:
            for signal in last_status.blocking_signals:
                if signal.signal_type.name == 'NETWORK_REQUESTS':
                    blocking_factors['pending_requests'] = signal.value
                elif signal.signal_type.name == 'DOM_MUTATIONS':
                    blocking_factors['recent_mutations'] = True
                elif signal.signal_type.name == 'CSS_ANIMATIONS':
                    blocking_factors['active_animations'] = signal.value
                elif signal.signal_type.name == 'LAYOUT_SHIFT':
                    blocking_factors['layout_shifting'] = signal.value
        
        message = (
            f"UI did not stabilize within {timeout}s. "
            "Run 'waitless doctor' for detailed analysis."
        )
        
        if blocking_factors:
            message += f" Blocking: {list(blocking_factors.keys())}"
        
        logger.warning(f"\n{'='*60}")
        logger.warning("WAITLESS TIMEOUT")
        logger.warning(f"{'='*60}")
        logger.warning(message)
        logger.warning(f"{'='*60}\n")
        
        raise StabilizationTimeout(
            message=message,
            timeout=timeout,
            blocking_factors=blocking_factors,
            timeline=self._timeline[-50:],
        )
    
    def _update_diagnostics(
        self,
        browser_state: Dict[str, Any],
        status: StabilityStatus
    ) -> None:
        """Update diagnostic information for the doctor command."""
        self._last_blocking_factors = {
            'pending_requests': browser_state.get('pending_requests', 0),
            'pending_request_details': browser_state.get('pending_request_details', []),
            'active_animations': browser_state.get('active_animations', 0),
            'layout_shifting': browser_state.get('layout_shifting', False),
            'last_mutation_time': browser_state.get('last_mutation_time', 0),
        }
        
        timeline = browser_state.get('timeline', [])
        self._timeline.extend(timeline)
        self._timeline = self._timeline[-200:]
    
    def _debug(self, message: str) -> None:
        """Log debug message if debug mode is enabled."""
        if self.config.debug_mode:
            logger.debug(f"[waitless] {message}")
    
    def get_diagnostics(self) -> Dict[str, Any]:
        """
        Get diagnostic information for the doctor command.
        
        Returns:
            Dictionary with diagnostic data
        """
        return {
            'config': {
                'timeout': self.config.timeout,
                'strictness': self.config.strictness,
                'network_idle_threshold': self.config.network_idle_threshold,
                'animation_detection': self.config.animation_detection,
            },
            'last_status': self._last_browser_state,  # Raw browser state with mutation_rate, etc.
            'blocking_factors': self._last_blocking_factors,
            'timeline': self._timeline[-50:],
            'instrumented': self._instrumented,
        }
    
    def reset(self) -> None:
        """Reset engine state (useful between tests)."""
        self._instrumented = False
        self._last_url = None
        self._last_status = None
        self._last_blocking_factors = {}
        self._timeline = []
