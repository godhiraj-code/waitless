"""
Selenium WebDriver integration layer.

Provides transparent stabilization for Selenium interactions through
the wrapper pattern (safer than monkey-patching).

Note: Wrapped elements behave like WebElements but are not identical.
This may affect equality checks or isinstance() calls in test code.
"""

import functools
import logging
from typing import Optional, Any, List, Dict, TYPE_CHECKING
from weakref import WeakValueDictionary

from .config import StabilizationConfig, DEFAULT_CONFIG
from .engine import StabilizationEngine


if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.remote.webelement import WebElement


logger = logging.getLogger('waitless')


_stabilized_drivers: WeakValueDictionary = WeakValueDictionary()


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
    
    def __init__(self, element: 'WebElement', engine: StabilizationEngine):
        self._element = element
        self._engine = engine
    
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying element."""
        attr = getattr(self._element, name)
        if name in self.INTERACTION_METHODS and callable(attr):
            return self._create_stabilized_method(attr, name)
        
        return attr
    
    def _create_stabilized_method(self, method: callable, name: str) -> callable:
        """Create a wrapper that stabilizes before calling the method."""
        @functools.wraps(method)
        def stabilized_method(*args, **kwargs):
            if self._engine.config.debug_mode:
                logger.debug(f"[waitless] Stabilizing before {name}()")
            
            self._engine.wait_for_stability()
            return method(*args, **kwargs)
        
        return stabilized_method
    
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
        
        return attr
    
    def _stabilized_find_element(self, *args, **kwargs) -> StabilizedWebElement:
        """Find element and wrap it for stabilization."""
        element = self._driver.find_element(*args, **kwargs)
        return StabilizedWebElement(element, self._engine)
    
    def _stabilized_find_elements(self, *args, **kwargs) -> List[StabilizedWebElement]:
        """Find elements and wrap them for stabilization."""
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
        self._engines: Dict[int, StabilizationEngine] = {}
        self._original_drivers: Dict[int, 'WebDriver'] = {}
        self._wrapped_drivers: Dict[int, StabilizedWebDriver] = {}
    
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
            
        Note:
            The returned driver wraps the original but is not a true WebDriver.
            If you need the original for framework integration, use .unwrapped
        """
        driver_id = id(driver)
        
        if driver_id in self._wrapped_drivers:
            existing = self._wrapped_drivers[driver_id]
            if config:
                existing._engine.config = config
            return existing
        
        effective_config = config or DEFAULT_CONFIG
        engine = StabilizationEngine(driver, effective_config)
        wrapped = StabilizedWebDriver(driver, engine)
        
        self._engines[driver_id] = engine
        self._original_drivers[driver_id] = driver
        self._wrapped_drivers[driver_id] = wrapped
        
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
        else:
            original = driver
            driver_id = id(driver)
        
        self._engines.pop(driver_id, None)
        self._original_drivers.pop(driver_id, None)
        self._wrapped_drivers.pop(driver_id, None)
        
        logger.info(f"[waitless] Stabilization disabled for driver {driver_id}")
        
        return original
    
    def get_engine(self, driver: 'WebDriver') -> Optional[StabilizationEngine]:
        """Get the engine for a driver (for diagnostics)."""
        if isinstance(driver, StabilizedWebDriver):
            return driver._engine
        return self._engines.get(id(driver))
    
    def is_stabilized(self, driver: 'WebDriver') -> bool:
        """Check if a driver is currently stabilized."""
        if isinstance(driver, StabilizedWebDriver):
            return True
        return id(driver) in self._wrapped_drivers


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
