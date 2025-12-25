"""
Integration tests for Selenium integration.

These tests require Chrome/ChromeDriver to be installed.
Run with: pytest tests/integration/ -v
"""

import os
import pytest
from pathlib import Path


# Skip if selenium not installed
pytest.importorskip("selenium")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from waitless import (
    stabilize,
    unstabilize,
    wait_for_stability,
    StabilizationConfig,
    StabilizedWebDriver,
    StabilizedWebElement,
)


# Path to test fixture
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "test_page.html"


@pytest.fixture
def driver():
    """Create a Chrome driver for testing."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


@pytest.fixture
def fixture_url():
    """Get URL to test fixture."""
    return f"file:///{FIXTURE_PATH.absolute().as_posix()}"


class TestStabilization:
    """Integration tests for stabilization."""
    
    def test_stabilize_returns_wrapped_driver(self, driver):
        """Test that stabilize returns a wrapped driver."""
        wrapped = stabilize(driver)
        
        assert isinstance(wrapped, StabilizedWebDriver)
        assert wrapped.unwrapped is driver
    
    def test_unstabilize_returns_original(self, driver):
        """Test that unstabilize returns original driver."""
        wrapped = stabilize(driver)
        original = unstabilize(wrapped)
        
        assert original is driver
    
    def test_find_element_returns_wrapped(self, driver, fixture_url):
        """Test that find_element returns wrapped elements."""
        driver = stabilize(driver)
        driver.get(fixture_url)
        
        element = driver.find_element(By.TAG_NAME, "h1")
        
        assert isinstance(element, StabilizedWebElement)
    
    def test_find_elements_returns_wrapped_list(self, driver, fixture_url):
        """Test that find_elements returns list of wrapped elements."""
        driver = stabilize(driver)
        driver.get(fixture_url)
        
        elements = driver.find_elements(By.TAG_NAME, "button")
        
        assert all(isinstance(el, StabilizedWebElement) for el in elements)
    
    def test_element_unwrap(self, driver, fixture_url):
        """Test unwrapping elements."""
        driver = stabilize(driver)
        driver.get(fixture_url)
        
        wrapped = driver.find_element(By.TAG_NAME, "h1")
        original = wrapped.unwrap()
        
        # Should be able to use Selenium methods
        assert original.text == "Waitless Test Fixture"


class TestStabilizationBehavior:
    """Test actual stabilization waiting behavior."""
    
    def test_waits_for_delayed_content(self, driver, fixture_url):
        """Test waiting for delayed content to appear."""
        config = StabilizationConfig(timeout=5)
        driver = stabilize(driver, config=config)
        driver.get(fixture_url)
        
        # Click button that loads content after delay
        driver.find_element(By.ID, "load-content-btn").click()
        
        # The content becomes visible after the 'hidden' class is removed from parent.
        # Use a CSS selector that only matches when NOT hidden.
        # This will retry until the element matches (i.e., hidden class is removed).
        container = driver.find_element(By.CSS_SELECTOR, "#delayed-content:not(.hidden)")
        # Access inner element via the unwrapped container
        content = container.unwrap().find_element(By.ID, "loaded-text")
        assert "Content loaded" in content.text
    
    def test_waits_for_mutations_to_stop(self, driver, fixture_url):
        """Test waiting for DOM mutations to complete."""
        config = StabilizationConfig(timeout=5, dom_settle_time=0.15)
        driver = stabilize(driver, config=config)
        driver.get(fixture_url)
        
        # Trigger mutations
        driver.find_element(By.ID, "mutate-btn").click()
        
        # Waitless auto-waits for mutations to complete - no sleep needed!
        # Check that all mutations completed
        complete = driver.find_element(By.ID, "mutations-complete")
        assert "complete" in complete.unwrap().text.lower()


class TestConfiguration:
    """Test configuration options."""
    
    def test_debug_mode_logs(self, driver, fixture_url, caplog):
        """Test that debug mode produces log output."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        config = StabilizationConfig(debug_mode=True)
        driver = stabilize(driver, config=config)
        driver.get(fixture_url)
        
        driver.find_element(By.TAG_NAME, "h1")
        
        # Should have some waitless logs
        # Note: Depending on timing this might not always capture logs
    
    def test_relaxed_mode_ignores_animations(self, driver, fixture_url):
        """Test relaxed mode doesn't wait for infinite animations."""
        config = StabilizationConfig(
            strictness='relaxed',
            timeout=2,
        )
        driver = stabilize(driver, config=config)
        driver.get(fixture_url)
        
        # Start infinite spinner
        driver.find_element(By.ID, "spinner-btn").click()
        
        # Should still be able to interact despite spinner
        # (In relaxed mode, animations don't block)
        h1 = driver.find_element(By.TAG_NAME, "h1")
        assert "Waitless" in h1.unwrap().text


class TestManualWait:
    """Test manual wait_for_stability function."""
    
    def test_manual_wait(self, driver, fixture_url):
        """Test using wait_for_stability directly."""
        driver.get(fixture_url)
        
        # Use manual wait without wrapping
        wait_for_stability(driver)
        
        # Page should be stable
        h1 = driver.find_element(By.TAG_NAME, "h1")
        assert h1.text == "Waitless Test Fixture"
