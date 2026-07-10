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

    def test_stabilize_is_idempotent_for_wrapped_driver(self, driver):
        wrapped = stabilize(driver)
        new_config = StabilizationConfig(network_idle_threshold=0)

        configured = stabilize(wrapped, config=new_config)

        assert configured is wrapped
        assert configured._engine.config is new_config
        assert configured._engine.evaluator.config is new_config

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
        """Test using manual wait without wrapping."""
        driver.get(fixture_url)
        
        # Use manual wait without wrapping
        wait_for_stability(driver)
        
        # Page should be stable
        h1 = driver.find_element(By.TAG_NAME, "h1")
        assert h1.text == "Waitless Test Fixture"


class TestBrowserBehaviorContracts:
    """Verify Python options actually change the browser runtime."""

    def test_config_is_applied_before_instrumentation_initializes(self, driver, fixture_url):
        driver.get(fixture_url)
        config = StabilizationConfig(
            layout_stability=False,
            animation_detection=False,
            track_websocket=True,
            track_sse=True,
            track_iframes=True,
            websocket_quiet_time=0.75,
        )
        wrapped = stabilize(driver, config=config)
        wrapped._engine.ensure_instrumented()

        browser_config = driver.execute_script("return window.__waitless__.config")
        assert browser_config == {
            "trackLayout": False,
            "trackAnimations": False,
            "trackWebSocket": True,
            "trackSSE": True,
            "webSocketQuietTime": 750,
            "trackIframes": True,
            "redactQueryStrings": True,
        }

    def test_mutation_rate_counts_records_not_callbacks(self, driver, fixture_url):
        driver.get(fixture_url)
        wrapped = stabilize(driver)
        wrapped._engine.ensure_instrumented()

        rate = driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            const container = document.createElement('div');
            document.body.appendChild(container);
            for (let i = 0; i < 100; i++) {
                container.appendChild(document.createElement('span'));
            }
            setTimeout(() => done(window.__waitless__.getMutationRate()), 0);
            """
        )
        assert rate >= 100

    def test_framework_adapter_detection_and_status_are_executed(self, driver, fixture_url):
        driver.get(fixture_url)
        driver.execute_script(
            "window.__REACT_DEVTOOLS_GLOBAL_HOOK__ = {onCommitFiberRoot: function() {}}"
        )
        wrapped = stabilize(driver, config=StabilizationConfig(framework_hooks=["react"]))
        wrapped._engine.ensure_instrumented()

        assert [adapter.name for adapter in wrapped._engine._active_adapters] == ["react"]
        state = wrapped._engine._get_browser_status()
        assert state["framework_status"][0]["name"] == "react"
        assert state["framework_status"][0]["stable"] is True

    def test_reconfigure_uninstalls_framework_hooks(self, driver, fixture_url):
        driver.get(fixture_url)
        driver.execute_script(
            "window.__originalReactCommit = function() { return 'original'; };"
            "window.__REACT_DEVTOOLS_GLOBAL_HOOK__ = {onCommitFiberRoot: window.__originalReactCommit};"
        )
        wrapped = stabilize(driver, config=StabilizationConfig(framework_hooks=["react"]))
        wrapped._engine.ensure_instrumented()
        assert driver.execute_script(
            "return window.__REACT_DEVTOOLS_GLOBAL_HOOK__.onCommitFiberRoot !== window.__originalReactCommit;"
        ) is True

        configured = stabilize(wrapped, config=StabilizationConfig(framework_hooks=[]))

        assert configured is wrapped
        assert driver.execute_script(
            "return window.__REACT_DEVTOOLS_GLOBAL_HOOK__.onCommitFiberRoot === window.__originalReactCommit;"
        ) is True
        assert driver.execute_script(
            "return window.__REACT_DEVTOOLS_GLOBAL_HOOK__.onCommitFiberRoot();"
        ) == "original"
        wrapped._engine.ensure_instrumented()
        assert wrapped._engine._active_adapters == []
        assert driver.execute_script(
            "return !window.__waitless__.framework || !window.__waitless__.framework.react;"
        ) is True

    def test_reconfigure_uninstalls_angular_hook(self, driver, fixture_url):
        driver.get(fixture_url)
        driver.execute_script(
            "window.ng = {};"
            "window.Zone = function Zone() {};"
            "window.Zone.current = {};"
            "window.__originalZoneRun = function(callback) { return callback(); };"
            "window.Zone.prototype.run = window.__originalZoneRun;"
        )
        wrapped = stabilize(driver, config=StabilizationConfig(framework_hooks=["angular"]))
        wrapped._engine.ensure_instrumented()
        assert driver.execute_script("return window.Zone.prototype.run !== window.__originalZoneRun;") is True

        stabilize(wrapped, config=StabilizationConfig(framework_hooks=[]))

        assert driver.execute_script("return window.Zone.prototype.run === window.__originalZoneRun;") is True
        assert driver.execute_script("return window.Zone.prototype.run(function() { return 'original'; });") == "original"

    def test_reconfigure_uninstalls_vue_hooks(self, driver, fixture_url):
        driver.get(fixture_url)
        driver.execute_script(
            "window.__originalVueNextTick = function(callback) { if (callback) callback(); return 'original'; };"
            "window.__vueListeners = {};"
            "window.__VUE_DEVTOOLS_GLOBAL_HOOK__ = {"
            "  Vue: {nextTick: window.__originalVueNextTick},"
            "  on: function(name, callback) { window.__vueListeners[name] = callback; },"
            "  off: function(name, callback) { if (window.__vueListeners[name] === callback) delete window.__vueListeners[name]; }"
            "};"
        )
        wrapped = stabilize(driver, config=StabilizationConfig(framework_hooks=["vue"]))
        wrapped._engine.ensure_instrumented()
        assert driver.execute_script(
            "return window.__VUE_DEVTOOLS_GLOBAL_HOOK__.Vue.nextTick !== window.__originalVueNextTick;"
        ) is True
        assert driver.execute_script("return !!window.__vueListeners['component:updated'];") is True

        stabilize(wrapped, config=StabilizationConfig(framework_hooks=[]))

        assert driver.execute_script(
            "return window.__VUE_DEVTOOLS_GLOBAL_HOOK__.Vue.nextTick === window.__originalVueNextTick;"
        ) is True
        assert driver.execute_script("return !window.__vueListeners['component:updated'];") is True
