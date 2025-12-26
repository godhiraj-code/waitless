"""
Waitless - Zero-wait UI automation stabilization library.

Eliminate explicit waits and sleeps in UI automation by automatically
waiting for true UI stability instead of time-based conditions.

Basic Usage:
    from waitless import stabilize
    
    driver = webdriver.Chrome()
    driver = stabilize(driver)  # That's it!
    
    # All interactions now auto-wait for stability
    driver.find_element(By.ID, "button").click()

Configuration:
    from waitless import stabilize, StabilizationConfig
    
    config = StabilizationConfig(
        timeout=5,                # Max wait time
        strictness='strict',      # All signals must be stable
        debug_mode=True           # Enable logging
    )
    
    driver = stabilize(driver, config=config)

Manual Stabilization:
    from waitless import wait_for_stability
    
    wait_for_stability(driver)  # Explicit wait
    driver.find_element(...).click()

Disable:
    from waitless import unstabilize
    
    driver = unstabilize(driver)  # Back to original behavior
"""

__version__ = '0.3.2'
__author__ = 'Dhiraj Das'

# Public API
from .config import StabilizationConfig, DEFAULT_CONFIG
from .selenium_integration import (
    stabilize,
    unstabilize,
    wait_for_stability,
    get_diagnostics,
    StabilizedWebDriver,
    StabilizedWebElement,
)
from .exceptions import (
    WaitlessError,
    StabilizationTimeout,
    InstrumentationError,
    ConfigurationError,
    NotStabilizedError,
)
from .engine import StabilizationEngine
from .diagnostics import DiagnosticReport, generate_report, print_report

__all__ = [
    # Version
    '__version__',
    
    # Main API
    'stabilize',
    'unstabilize',
    'wait_for_stability',
    'get_diagnostics',
    
    # Configuration
    'StabilizationConfig',
    'DEFAULT_CONFIG',
    
    # Types
    'StabilizedWebDriver',
    'StabilizedWebElement',
    'StabilizationEngine',
    
    # Exceptions
    'WaitlessError',
    'StabilizationTimeout',
    'InstrumentationError',
    'ConfigurationError',
    'NotStabilizedError',
    
    # Diagnostics
    'DiagnosticReport',
    'generate_report',
    'print_report',
]
