"""
Selenium WebDriver integration layer.

Provides transparent stabilization for Selenium interactions through
the wrapper pattern (safer than monkey-patching).

Note: Wrapped elements behave like WebElements but are not identical.
This may affect equality checks or isinstance() calls in test code.
"""

import functools
import logging
import time
import weakref
from typing import Optional, Any, Callable, List, Dict, TYPE_CHECKING
from weakref import WeakKeyDictionary

from .config import StabilizationConfig, DEFAULT_CONFIG
from .engine import StabilizationEngine

try:
    from selenium.webdriver.remote.webelement import WebElement as SeleniumWebElement
except ImportError:  # Keep importing waitless possible for documentation builds.
    SeleniumWebElement = ()


if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.remote.webelement import WebElement


logger = logging.getLogger('waitless')


FINGERPRINT_SCRIPT = """
const element = arguments[0];
if (!element.isConnected) return null;
const text = node => node && node.getClientRects().length
    ? (node.innerText || '').trim().slice(0, 200) : '';
return [
    element.tagName.toLowerCase(),
    text(element),
    ['id', 'name', 'data-testid', 'aria-label'].map(name => element.getAttribute(name)),
    text(element.parentElement)
];
"""


def _remaining(deadline: float, error: Exception) -> float:
    """Never start another wait after the public call's budget is exhausted."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise error
    return remaining


def _settle(engine, deadline, error):
    engine.wait_for_stability(timeout=_remaining(deadline, error))
    _remaining(deadline, error)


def _lookup(
    find, engine, deadline, error, *, settle_after=False, retry_missing=True,
    preserve_not_found=False,
):
    from selenium.common.exceptions import NoSuchElementException

    while True:
        _remaining(deadline, error)
        try:
            element = find()
            if settle_after:
                _settle(engine, deadline, error)
                element = find()
            _remaining(deadline, error)
            return element
        except NoSuchElementException as exc:
            if not retry_missing:
                raise
            if preserve_not_found:
                error = exc
            time.sleep(min(engine.config.poll_interval, _remaining(deadline, error)))


def _find_element(context, engine, args, kwargs, *, retry_missing=False):
    from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

    timeout = engine.config.timeout
    deadline = time.monotonic() + timeout
    locator = f"{args}" + (f" {kwargs}" if kwargs else "")
    error = NoSuchElementException(f"Element not found within {timeout}s: {locator}")
    find = functools.partial(context.find_element, *args, **kwargs)
    while True:
        _settle(engine, deadline, error)
        element = _lookup(
            find, engine, deadline, error,
            settle_after=True, retry_missing=retry_missing, preserve_not_found=True,
        )
        try:
            return StabilizedWebElement(
                element, engine, refind=find, deadline=deadline,
            )
        except StaleElementReferenceException as exc:
            # The caller has not received an element yet. Retry a redraw during
            # the snapshot without starting a fresh timeout budget.
            error = exc
            time.sleep(min(engine.config.poll_interval, _remaining(deadline, exc)))


class _StabilizedSearchContext:
    """Keep element lookups from contexts such as ShadowRoot stabilized."""

    def __init__(self, context: Any, engine: StabilizationEngine):
        self._context = context
        self._engine = engine

    def find_element(self, *args, **kwargs) -> 'StabilizedWebElement':
        return _find_element(self._context, self._engine, args, kwargs)

    def find_elements(self, *args, **kwargs) -> List['StabilizedWebElement']:
        self._engine.wait_for_stability()
        return [
            StabilizedWebElement(element, self._engine)
            for element in self._context.find_elements(*args, **kwargs)
        ]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._context, name)

    def unwrap(self) -> Any:
        return self._context


class StabilizedWebElement:
    """
    Wrapper around WebElement that auto-waits for stability before interactions.
    
    This wrapper:
    - Intercepts click(), send_keys(), submit(), clear() to wait for stability
    - Delegates all other attributes/methods to the underlying element
    - Preserves the original element for direct access if needed
    
    IMPORTANT: This wrapper is NOT a WebElement subclass.
    - isinstance(wrapped, WebElement) will return False
    - Equality checks may behave unexpectedly
    - Use .unwrap() to get the original element if needed
    """
    
    INTERACTION_METHODS = {'click', 'send_keys', 'submit', 'clear'}
    
    def __init__(
        self,
        element: 'WebElement',
        engine: StabilizationEngine,
        refind: Optional[Callable[[], 'WebElement']] = None,
        *,
        deadline: Optional[float] = None,
    ):
        self._element = element
        self._engine = engine
        self._refind = refind
        # Capture while the original is live, not after a stale-reference error.
        self._fingerprint = None
        if refind:
            if deadline is None:
                deadline = time.monotonic() + engine.config.timeout
            self._fingerprint = self._capture_fingerprint(element, deadline)

    def _capture_fingerprint(self, element, deadline):
        from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

        error = TimeoutException("Timed out reading element fingerprint")
        _remaining(deadline, error)
        fingerprint = self._engine.driver.execute_script(
            FINGERPRINT_SCRIPT, element,
        )
        _remaining(deadline, error)
        if fingerprint is None:
            raise StaleElementReferenceException("Element became stale while reading its fingerprint")
        return fingerprint
    
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying element."""
        attr = getattr(self._element, name)
        if name in self.INTERACTION_METHODS and callable(attr):
            return self._create_stabilized_method(attr, name)
        if name == 'find_element':
            return self._stabilized_find_element
        if name == 'find_elements':
            return self._stabilized_find_elements
        if name == 'shadow_root':
            return _StabilizedSearchContext(attr, self._engine)
        
        return attr

    def _stabilized_find_element(self, *args, **kwargs) -> 'StabilizedWebElement':
        """Keep elements found below this element inside the wrapper boundary."""
        return _find_element(self._element, self._engine, args, kwargs)

    def _stabilized_find_elements(self, *args, **kwargs) -> List['StabilizedWebElement']:
        """Return wrapped descendants while preserving Selenium's list contract."""
        self._engine.wait_for_stability()
        elements = self._element.find_elements(*args, **kwargs)
        return [StabilizedWebElement(element, self._engine) for element in elements]
    
    def _create_stabilized_method(self, method: callable, name: str) -> callable:
        """Create a wrapper that stabilizes before calling the method."""
        @functools.wraps(method)
        def stabilized_method(*args, **kwargs):
            if self._engine.config.debug_mode:
                logger.debug(f"[waitless] Stabilizing before {name}()")
            
            if name == 'click':
                return self._click(*args, **kwargs)
            self._engine.wait_for_stability()
            return method(*args, **kwargs)
        
        return stabilized_method

    def _click(self, *args, **kwargs):
        """Wait for enabled state and recover once from a locator-backed stale click."""
        from selenium.common.exceptions import (
            NoSuchElementException, StaleElementReferenceException, TimeoutException,
        )

        timeout = self._engine.config.timeout
        deadline = time.monotonic() + timeout
        tag, text = self._fingerprint[:2] if self._fingerprint is not None else (None, None)
        label = f"Element <{tag}> {text!r}" if tag is not None else "Element"
        error = TimeoutException(f"{label} was not enabled after {timeout}s")
        for attempt in range(2):
            _settle(self._engine, deadline, error)
            if attempt:
                missing = NoSuchElementException(
                    f"Element <{tag}> {text!r} is no longer on the page"
                )
                candidate = _lookup(self._refind, self._engine, deadline, missing)
                if self._capture_fingerprint(candidate, deadline) != self._fingerprint:
                    raise StaleElementReferenceException(
                        "Element changed; Waitless refused to click a different element "
                        f"instead of <{tag}> {text!r}."
                    )
                _remaining(deadline, error)
                self._element = candidate
            try:
                while True:
                    _remaining(deadline, error)
                    if self._element.is_enabled():
                        break
                    time.sleep(min(
                        self._engine.config.poll_interval, _remaining(deadline, error),
                    ))
                _remaining(deadline, error)
                return self._element.click(*args, **kwargs)
            except StaleElementReferenceException:
                if attempt or self._refind is None:
                    raise
            except TimeoutException as exc:
                if exc is error and self._fingerprint is None:
                    # List/script results need no identity snapshot on success.
                    # Only enrich an actual enabled timeout, without another wait
                    # or retry. A vanished element must not mask the original error.
                    try:
                        fingerprint = self._engine.driver.execute_script(
                            FINGERPRINT_SCRIPT, self._element,
                        )
                    except StaleElementReferenceException:
                        fingerprint = None
                    if fingerprint is not None:
                        tag, text = fingerprint[:2]
                        error.msg = f"Element <{tag}> {text!r} was not enabled after {timeout}s"
                raise
    
    @property
    def wrapped_element(self) -> 'WebElement':
        """Access the underlying WebElement directly."""
        return self._element
    
    def unwrap(self) -> 'WebElement':
        """Get the original WebElement (alias for wrapped_element)."""
        return self._element
    
    def __repr__(self) -> str:
        return f"<StabilizedWebElement wrapping {self._element}>"
    
    def __eq__(self, other: Any) -> bool:
        """Compare underlying elements for equality."""
        if isinstance(other, StabilizedWebElement):
            return self._element == other._element
        return self._element == other
    
    def __hash__(self) -> int:
        return hash(self._element)


class StabilizedWebDriver:
    """
    Wrapper around WebDriver that returns stabilized elements.
    
    This wrapper:
    - Wraps find_element/find_elements to return StabilizedWebElement
    - Triggers stabilization before get() navigation
    - Preserves all other WebDriver functionality
    """
    
    def __init__(self, driver: 'WebDriver', engine: StabilizationEngine):
        self._driver = driver
        self._engine = engine
    
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying driver."""
        attr = getattr(self._driver, name)
        if name == 'find_element':
            return self._stabilized_find_element
        elif name == 'find_elements':
            return self._stabilized_find_elements
        elif name in {'get', 'refresh', 'back', 'forward'}:
            return self._create_stabilized_navigation(attr, name)
        elif name == 'execute_async_script':
            return self._create_stabilized_execute_async_script
        elif name ==  'execute_script':
            return self._create_stabilized_execute_script
        return attr

    def _unwrap_script_arg(self, value):
        """Recursively replace wrapped elements in JavaScript arguments."""
        if isinstance(value, StabilizedWebElement):
            return value.unwrap()
        if isinstance(value, _StabilizedSearchContext):
            return value.unwrap()
        if isinstance(value, dict):
            return {
                key: self._unwrap_script_arg(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._unwrap_script_arg(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._unwrap_script_arg(item) for item in value)
        return value

    def _unwrap_args_tuple(self, *args):
        return tuple(self._unwrap_script_arg(arg) for arg in args)

    def _wrap_response(self, value):
        if isinstance(value, dict):
            return {
                key: self._wrap_response(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._wrap_response(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._wrap_response(item) for item in value)
        if SeleniumWebElement and isinstance(value, SeleniumWebElement):
            return StabilizedWebElement(value, self._engine)
        return value

    def _create_stabilized_execute_async_script(self, script: str, *args):
        args_unwrapped = self._unwrap_args_tuple(*args)
        response = self._driver.execute_async_script(script, *args_unwrapped)
        return self._wrap_response(response)

    def _create_stabilized_execute_script(self, script: str, *args):
        args_unwrapped = self._unwrap_args_tuple(*args)
        response = self._driver.execute_script(script, *args_unwrapped)
        return self._wrap_response(response)

    def _create_stabilized_navigation(self, method: callable, name: str) -> callable:
        """Wait for the destination document after a synchronous navigation."""
        @functools.wraps(method)
        def stabilized_navigation(*args, **kwargs):
            result = method(*args, **kwargs)
            self._engine.reset()
            self._engine.wait_for_stability()
            return result
        return stabilized_navigation
    
    def _stabilized_find_element(self, *args, **kwargs) -> StabilizedWebElement:
        """
        Find element with automatic waiting.
        
        This method:
        1. Waits for page stability first
        2. Tries to find the element
        3. If element not found, retries until timeout
        4. Waits for stability again and re-finds using the same locator
        
        This eliminates the need for explicit WebDriverWait in test code.
        """
        return _find_element(
            self._driver, self._engine, args, kwargs, retry_missing=True,
        )
    
    def _stabilized_find_elements(self, *args, **kwargs) -> List[StabilizedWebElement]:
        """
        Find elements with automatic waiting.
        
        Similar to find_element but returns list (may be empty).
        """
        # Match Selenium's contract: one lookup and an immediate empty list when
        # there are no matches. Only the page-stability wait is added.
        self._engine.wait_for_stability()
        elements = self._driver.find_elements(*args, **kwargs)
        return [StabilizedWebElement(el, self._engine) for el in elements]
    
    @property
    def unwrapped(self) -> 'WebDriver':
        """Access the underlying WebDriver directly."""
        return self._driver
    
    def wait_for_stability(self, timeout: Optional[float] = None):
        """Manually trigger stabilization."""
        return self._engine.wait_for_stability(timeout)
    
    def __repr__(self) -> str:
        return f"<StabilizedWebDriver wrapping {self._driver}>"


class SeleniumIntegration:
    """
    Main integration class for Selenium.
    
    Provides the stabilize() and unstabilize() functions.
    """
    
    def __init__(self):
        # Both keys and values are weak. A registry entry cannot keep either the
        # Selenium driver or its wrapper alive after user code releases them.
        self._wrapped_drivers: WeakKeyDictionary = WeakKeyDictionary()

    def _lookup(self, driver: 'WebDriver') -> Optional[StabilizedWebDriver]:
        ref = self._wrapped_drivers.get(driver)
        return ref() if ref is not None else None
    
    def stabilize(
        self,
        driver: 'WebDriver',
        config: Optional[StabilizationConfig] = None
    ) -> StabilizedWebDriver:
        """
        Enable automatic stabilization for a WebDriver.
        
        Args:
            driver: Selenium WebDriver instance
            config: Optional configuration overrides
            
        Returns:
            StabilizedWebDriver that auto-waits before interactions
            
        Raises:
            TypeError: If driver is not a valid WebDriver instance
            
        Note:
            The returned driver wraps the original but is not a true WebDriver.
            If you need the original for framework integration, use .unwrapped
        """
        if isinstance(driver, StabilizedWebDriver):
            if config is not None:
                driver._engine.configure(config)
            return driver

        # Validate driver is a WebDriver-like object
        if driver is None:
            raise TypeError("driver cannot be None")
        
        required_attrs = ['execute_script', 'find_element', 'current_url']
        missing = [attr for attr in required_attrs if not hasattr(driver, attr)]
        if missing:
            raise TypeError(
                f"driver does not appear to be a valid WebDriver. "
                f"Missing required attributes: {missing}"
            )
        
        driver_id = id(driver)
        existing = self._lookup(driver)
        if existing is not None:
            if config:
                existing._engine.configure(config)
            return existing
        
        effective_config = config or DEFAULT_CONFIG
        engine = StabilizationEngine(driver, effective_config)
        wrapped = StabilizedWebDriver(driver, engine)
        self._wrapped_drivers[driver] = weakref.ref(wrapped)
        
        if effective_config.debug_mode:
            logger.info(f"[waitless] Stabilization enabled for driver {driver_id}")
        
        return wrapped
    
    def unstabilize(self, driver: 'WebDriver') -> 'WebDriver':
        """
        Disable stabilization and return the original driver.
        
        Args:
            driver: Either the original driver or a StabilizedWebDriver
            
        Returns:
            The original unwrapped WebDriver
        """
        if isinstance(driver, StabilizedWebDriver):
            original = driver.unwrapped
            driver_id = id(original)
            engine = driver._engine
        else:
            original = driver
            driver_id = id(driver)
            wrapped = self._lookup(original)
            engine = wrapped._engine if wrapped is not None else None

        if engine is not None:
            engine.teardown()
        
        self._wrapped_drivers.pop(original, None)
        
        logger.info(f"[waitless] Stabilization disabled for driver {driver_id}")
        
        return original
    
    def get_engine(self, driver: 'WebDriver') -> Optional[StabilizationEngine]:
        """Get the engine for a driver (for diagnostics)."""
        if isinstance(driver, StabilizedWebDriver):
            return driver._engine
        wrapped = self._lookup(driver)
        return wrapped._engine if wrapped is not None else None
    
    def is_stabilized(self, driver: 'WebDriver') -> bool:
        """Check if a driver is currently stabilized."""
        if isinstance(driver, StabilizedWebDriver):
            return True
        return self._lookup(driver) is not None


_integration = SeleniumIntegration()


def stabilize(
    driver: 'WebDriver',
    config: Optional[StabilizationConfig] = None
) -> StabilizedWebDriver:
    """
    Enable automatic stabilization for a WebDriver.
    
    This is the main entry point for waitless.
    
    Example:
        from waitless import stabilize
        
        driver = webdriver.Chrome()
        driver = stabilize(driver)  # Now auto-waits!
        
        driver.find_element(By.ID, "button").click()  # Auto-stabilizes
    
    Args:
        driver: Selenium WebDriver instance
        config: Optional StabilizationConfig for customization
        
    Returns:
        StabilizedWebDriver that auto-waits before interactions
    """
    return _integration.stabilize(driver, config)


def unstabilize(driver: 'WebDriver') -> 'WebDriver':
    """
    Disable stabilization and return the original driver.
    
    Example:
        driver = unstabilize(driver)  # Back to normal
    """
    return _integration.unstabilize(driver)


def wait_for_stability(
    driver: 'WebDriver',
    timeout: Optional[float] = None
) -> None:
    """
    Manually wait for UI stability.
    
    Use this for explicit stabilization without wrapping interactions.
    
    Example:
        wait_for_stability(driver)
        driver.find_element(By.ID, "button").click()
    """
    if isinstance(driver, StabilizedWebDriver):
        driver.wait_for_stability(timeout)
    else:
        engine = StabilizationEngine(driver)
        engine.wait_for_stability(timeout)


def get_diagnostics(driver: 'WebDriver') -> Optional[Dict[str, Any]]:
    """Get diagnostic information for a stabilized driver."""
    engine = _integration.get_engine(driver)
    if engine:
        return engine.get_diagnostics()
    return None
