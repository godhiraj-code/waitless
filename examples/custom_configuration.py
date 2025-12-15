"""
Example: Custom configuration for waitless.

Shows how to customize stabilization behavior for different scenarios.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from waitless import stabilize, StabilizationConfig


def example_strict_mode():
    """
    Strict mode: Wait for ALL stability signals.
    
    Use when: Testing critical flows where even small UI changes matter.
    """
    config = StabilizationConfig.strict()
    # Equivalent to:
    # config = StabilizationConfig(
    #     strictness='strict',
    #     timeout=5.0,
    #     animation_detection=True,
    #     layout_stability=True,
    # )
    
    driver = webdriver.Chrome()
    driver = stabilize(driver, config=config)
    
    # All interactions now wait for complete stability
    driver.get("https://example.com")
    driver.find_element(By.TAG_NAME, "h1").click()
    
    driver.quit()


def example_relaxed_mode():
    """
    Relaxed mode: Only wait for DOM stability.
    
    Use when: App has infinite animations or background polling.
    """
    config = StabilizationConfig.relaxed()
    # Equivalent to:
    # config = StabilizationConfig(
    #     strictness='relaxed',
    #     network_idle_threshold=2,
    #     animation_detection=False,
    #     layout_stability=False,
    # )
    
    driver = webdriver.Chrome()
    driver = stabilize(driver, config=config)
    
    driver.get("https://example.com")
    driver.find_element(By.TAG_NAME, "h1").click()
    
    driver.quit()


def example_custom_network_threshold():
    """
    Custom network threshold for apps with background traffic.
    
    Use when: Analytics, WebSocket, or polling cause constant network activity.
    """
    config = StabilizationConfig(
        network_idle_threshold=3,  # Allow up to 3 pending requests
        timeout=15.0,              # Longer timeout for slow APIs
        debug_mode=True,           # Enable logging for troubleshooting
    )
    
    driver = webdriver.Chrome()
    driver = stabilize(driver, config=config)
    
    driver.get("https://example.com")
    driver.find_element(By.TAG_NAME, "h1").click()
    
    driver.quit()


def example_ci_configuration():
    """
    CI-optimized configuration.
    
    Use when: Running in CI where you want verbose logging.
    """
    config = StabilizationConfig.ci()
    # Equivalent to:
    # config = StabilizationConfig(
    #     timeout=15.0,
    #     debug_mode=True,
    #     strictness='normal',
    # )
    
    driver = webdriver.Chrome()
    driver = stabilize(driver, config=config)
    
    driver.get("https://example.com")
    driver.find_element(By.TAG_NAME, "h1").click()
    
    driver.quit()


def example_per_test_override():
    """
    Override configuration for specific tests.
    """
    # Base configuration
    base_config = StabilizationConfig(timeout=10)
    
    driver = webdriver.Chrome()
    driver = stabilize(driver, config=base_config)
    
    # For a slow page, use longer timeout
    slow_config = base_config.with_overrides(timeout=30)
    
    # Re-stabilize with new config
    from waitless import unstabilize
    driver = unstabilize(driver)
    driver = stabilize(driver, config=slow_config)
    
    driver.get("https://slow-website.example")
    
    driver.quit()


if __name__ == "__main__":
    print("Run individual examples as needed")
