"""
Core stabilization engine.

This is the heart of waitless - it manages JavaScript injection,
polls for stability status, and makes the final stability decision.
"""

import time
import threading
import logging
from urllib.parse import urlsplit, urlunsplit
from typing import Optional, Dict, Any, TYPE_CHECKING

# Import Selenium exceptions for specific error handling
try:
    from selenium.common.exceptions import (
        WebDriverException,
        JavascriptException,
        NoSuchWindowException,
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    # Fallback for when selenium is not installed
    WebDriverException = Exception
    JavascriptException = Exception
    NoSuchWindowException = Exception
    SELENIUM_AVAILABLE = False

from .config import StabilizationConfig, DEFAULT_CONFIG
from .signals import SignalEvaluator, StabilityStatus
from .instrumentation import (
    INSTRUMENTATION_SCRIPT,
    CHECK_ALIVE_SCRIPT,
    GET_STATUS_SCRIPT,
)
from .adapters import get_adapter
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
        self._active_adapters: list = []
        
        if self.config.debug_mode:
            logging.basicConfig(level=logging.DEBUG)
            logger.setLevel(logging.DEBUG)

    def configure(self, config: StabilizationConfig) -> None:
        """Apply a new config and force browser instrumentation to be rebuilt."""
        self.config = config
        self.evaluator = SignalEvaluator(config)
        if self._instrumented:
            try:
                self._uninstall_adapters()
                self.driver.execute_script(
                    "if (window.__waitless__) { window.__waitless__.destroy(); }"
                )
            except (JavascriptException, WebDriverException, NoSuchWindowException):
                # A navigation may already have discarded the old page. The next
                # wait will inject into the current document regardless.
                pass
        self._active_adapters = []
        self.reset()

    def _browser_config(self) -> Dict[str, Any]:
        return {
            'trackLayout': self.config.layout_stability,
            'trackAnimations': self.config.animation_detection,
            'trackWebSocket': self.config.track_websocket,
            'trackSSE': self.config.track_sse,
            'webSocketQuietTime': self.config.websocket_quiet_time * 1000,
            'trackIframes': self.config.track_iframes,
            'redactQueryStrings': True,
        }
    
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
        except (WebDriverException, NoSuchWindowException) as e:
            self._debug(f"Could not get current URL: {e}")
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
        except (JavascriptException, WebDriverException, NoSuchWindowException) as e:
            self._debug(f"Instrumentation check failed: {e}")
            return False
    
    def _uninstall_adapters(self) -> None:
        """Restore every browser API patched by active framework adapters."""
        for adapter in reversed(self._active_adapters):
            try:
                self.driver.execute_script("return " + adapter.uninstall_script.strip())
            except (JavascriptException, WebDriverException, NoSuchWindowException):
                # The page may have navigated or the adapter may already be gone.
                continue

    def _inject_instrumentation(self) -> None:
        """Inject configured JavaScript instrumentation and framework hooks."""
        try:
            self.driver.execute_script(INSTRUMENTATION_SCRIPT, self._browser_config())
            self._active_adapters = []
            for name in self.config.framework_hooks:
                adapter = get_adapter(name)
                detected = adapter and self.driver.execute_script(
                    "return " + adapter.detection_script.strip()
                )
                if detected:
                    installed = self.driver.execute_script(
                        "return " + adapter.instrumentation_script.strip()
                    )
                    if installed:
                        self._active_adapters.append(adapter)
            self._instrumented = True
            self._debug("Instrumentation injected successfully")
        except (JavascriptException, WebDriverException, NoSuchWindowException) as e:
            self._instrumented = False
            raise InstrumentationError(
                f"Failed to inject instrumentation: {e}",
                original_error=e
            ) from e
    
    def _get_browser_status(self) -> Optional[Dict[str, Any]]:
        """Get current stability status from browser."""
        try:
            state = self.driver.execute_script(GET_STATUS_SCRIPT)
            if state is not None and self._active_adapters:
                state['framework_status'] = [
                    {
                        'name': adapter.name,
                        **self.driver.execute_script(
                            "return " + adapter.get_status_script().strip()
                        ),
                    }
                    for adapter in self._active_adapters
                ]
            return state
        except (JavascriptException, WebDriverException, NoSuchWindowException) as e:
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
            self._last_browser_state = browser_state
            self._update_diagnostics(browser_state, status)
            
            if status.is_stable:
                self._debug(f"UI stable after {elapsed:.2f}s")
                return status
            
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
    
    @staticmethod
    def _redact_url(url: Any) -> str:
        """Remove query strings/fragments from diagnostic URLs by default."""
        value = str(url or 'unknown')
        parts = urlsplit(value)
        hostname = parts.hostname or ''
        if ':' in hostname and not hostname.startswith('['):
            hostname = f'[{hostname}]'
        try:
            port = parts.port
        except ValueError:
            port = None
        netloc = f'{hostname}:{port}' if port is not None else hostname
        return urlunsplit((parts.scheme, netloc, parts.path, '', ''))

    def _redact_details(self, details: Any) -> list:
        redacted = []
        for item in (details or []):
            clean = dict(item)
            for key in ('url', 'src'):
                if key in clean:
                    clean[key] = self._redact_url(clean[key])
            redacted.append(clean)
        return redacted

    def _redact_timeline(self, timeline: Any) -> list:
        result = []
        for entry in (timeline or []):
            clean = dict(entry)
            if isinstance(clean.get('data'), dict):
                data = dict(clean['data'])
                for key in ('url', 'src'):
                    if key in data:
                        data[key] = self._redact_url(data[key])
                clean['data'] = data
            result.append(clean)
        return result

    def _update_diagnostics(
        self,
        browser_state: Dict[str, Any],
        status: StabilityStatus
    ) -> None:
        """Update diagnostic information for the doctor command."""
        self._last_blocking_factors = {
            'pending_requests': browser_state.get('pending_requests', 0),
            'pending_request_details': self._redact_details(
                browser_state.get('pending_request_details')
            ),
            'active_animations': browser_state.get('active_animations', 0),
            'layout_shifting': browser_state.get('layout_shifting', False),
            'last_mutation_time': browser_state.get('last_mutation_time', 0),
            'mutation_rate': browser_state.get('mutation_rate', 0),
            'active_websockets': browser_state.get('active_websockets', 0),
            'last_websocket_activity': browser_state.get('last_websocket_activity', 0),
            'websocket_details': self._redact_details(browser_state.get('websocket_details')),
            'active_sse': browser_state.get('active_sse', 0),
            'last_sse_activity': browser_state.get('last_sse_activity', 0),
            'sse_details': self._redact_details(browser_state.get('sse_details')),
            'iframe_status': self._redact_details(browser_state.get('iframe_status')),
            'framework_status': browser_state.get('framework_status', []),
        }
        
        timeline = self._redact_timeline(browser_state.get('timeline'))
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
        browser_state = dict(self._last_browser_state or {})
        for key in ('pending_request_details', 'websocket_details', 'sse_details', 'iframe_status'):
            browser_state[key] = self._redact_details(browser_state.get(key))
        browser_state['timeline'] = self._redact_timeline(browser_state.get('timeline'))
        return {
            'schema_version': 1,
            'config': {
                'timeout': self.config.timeout,
                'dom_settle_time': self.config.dom_settle_time,
                'mutation_rate_threshold': self.config.mutation_rate_threshold,
                'network_idle_threshold': self.config.network_idle_threshold,
                'animation_detection': self.config.animation_detection,
                'layout_stability': self.config.layout_stability,
                'strictness': self.config.strictness,
                'poll_interval': self.config.poll_interval,
                'track_websocket': self.config.track_websocket,
                'track_sse': self.config.track_sse,
                'websocket_quiet_time': self.config.websocket_quiet_time,
                'framework_hooks': list(self.config.framework_hooks),
                'track_iframes': self.config.track_iframes,
            },
            'last_status': self._last_status.to_dict() if self._last_status else None,
            'browser_state': browser_state,
            'blocking_factors': dict(self._last_blocking_factors),
            'timeline': list(self._timeline[-50:]),
            'instrumented': self._instrumented,
        }
    
    def reset(self) -> None:
        """Reset engine state (useful between tests)."""
        self._instrumented = False
        self._last_url = None
        self._last_status = None
        self._last_blocking_factors = {}
        self._timeline = []
