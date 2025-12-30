# Waitless

[![CI](https://github.com/godhiraj-code/waitless/actions/workflows/ci.yml/badge.svg)](https://github.com/godhiraj-code/waitless/actions/workflows/ci.yml)

**Zero-wait UI automation stabilization for Selenium**

Eliminate explicit waits and sleeps by automatically detecting true UI stability.



## Installation

```bash
pip install waitless
```

## Quick Start

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from waitless import stabilize

# Create driver as usual
driver = webdriver.Chrome()

# Enable automatic stabilization - ONE LINE
driver = stabilize(driver)

# All interactions now auto-wait for stability
driver.get("https://example.com")
driver.find_element(By.ID, "login-button").click()  # ← Auto-waits!
driver.find_element(By.ID, "username").send_keys("user")  # ← Auto-waits!
```

## Why Waitless?

### The Problem

Automation tests fail because interactions happen while the UI is still changing:

- DOM mutations from React/Vue/Angular updates
- In-flight AJAX requests
- CSS animations and transitions
- Layout shifts from lazy-loaded content

### Traditional Solutions (and why they fail)

| Approach | Problem |
|----------|---------|
| `time.sleep(2)` | Too slow, still fails sometimes |
| `WebDriverWait` | Only checks one element, misses page-wide state |
| Retries | Masks the real problem, adds flakiness |

### The Waitless Solution

Waitless monitors the **entire page** for stability signals:

- ✅ DOM mutation activity (MutationObserver, including **Shadow DOM**)
- ✅ Pending network requests (XHR/fetch interception)
- ✅ CSS animations and transitions
- ✅ Layout stability (element movement)

When you interact, waitless ensures the page is truly ready.

## Configuration

```python
from waitless import stabilize, StabilizationConfig

config = StabilizationConfig(
    timeout=10,                    # Max wait time (seconds)
    mutation_rate_threshold=50,    # mutations/sec considered stable (allows animations)
    network_idle_threshold=2,      # Max pending requests (allows background traffic)
    animation_detection=True,      # Track CSS animations (non-blocking in normal mode)
    strictness='normal',           # 'strict' | 'normal' | 'relaxed'
    debug_mode=True                # Enable logging
)

driver = stabilize(driver, config=config)
```

### Strictness Levels

| Level | What It Waits For |
|-------|-------------------|
| `strict` | DOM + Network + Animations + Layout |
| `normal` | DOM + Network (default) |
| `relaxed` | DOM only |

### Factory Methods

```python
# For strict testing
config = StabilizationConfig.strict()

# For apps with background traffic
config = StabilizationConfig.relaxed()

# For CI environments
config = StabilizationConfig.ci()
```

## Manual Stabilization

If you don't want to wrap the driver:

```python
from waitless import wait_for_stability

wait_for_stability(driver)
driver.find_element(By.ID, "button").click()
```

## Disabling Stabilization

```python
from waitless import unstabilize

driver = unstabilize(driver)  # Back to original behavior
```

## Diagnostics

When tests fail, get detailed analysis:

```python
from waitless import get_diagnostics, StabilizationTimeout
from waitless.diagnostics import print_report

try:
    driver.find_element(By.ID, "slow-button").click()
except StabilizationTimeout as e:
    diagnostics = get_diagnostics(driver)
    print_report(engine)  # Print detailed report
```

### CLI Doctor Command

```bash
python -m waitless doctor --file diagnostics.json
```

Sample output:
```
+--------------------------------------------------------------------+
|                     WAITLESS STABILITY REPORT                      |
+--------------------------------------------------------------------+
| BLOCKING FACTORS:                                                  |
|   [!] NETWORK: 2 request(s) still pending                          |
|   -> GET /api/users                                                |
|   [!] ANIMATIONS: 1 active animation(s)                            |
+--------------------------------------------------------------------+
| SUGGESTIONS:                                                       |
|   1. Set network_idle_threshold=2 for background traffic           |
|   2. Use animation_detection=False for infinite spinners           |
+--------------------------------------------------------------------+
```

## Important Notes

### Network Threshold Warning

The default `network_idle_threshold=2` allows some background traffic.

Many apps have background traffic that never stops:
- Analytics calls
- Long polling
- Feature flags
- WebSocket heartbeats

If tests timeout frequently, try:
```python
config = StabilizationConfig(network_idle_threshold=2)
```

### Wrapped Elements

The stabilized driver returns wrapped elements that auto-wait. They behave like WebElements but:

- `isinstance(element, WebElement)` returns `False`
- Use `.unwrap()` to get the original element if needed

```python
element = driver.find_element(By.ID, "button")
original = element.unwrap()  # Gets the real WebElement
```

## v0.3.2 Limitations

- **Selenium only** - Playwright support planned for v1
- **Sync only** - No async/await support yet
- **Main frame only** - iframes not monitored
- **No Service Workers** - SW network requests not intercepted

See [CHANGELOG.md](CHANGELOG.md) for version history.

## API Reference

### Functions

| Function | Description |
|----------|-------------|
| `stabilize(driver, config=None)` | Enable auto-stabilization |
| `unstabilize(driver)` | Disable and return original driver |
| `wait_for_stability(driver, timeout=None)` | Manual one-time wait |
| `get_diagnostics(driver)` | Get diagnostic data |

### Classes

| Class | Description |
|-------|-------------|
| `StabilizationConfig` | Configuration options |
| `StabilizedWebDriver` | Wrapped driver with auto-wait |
| `StabilizedWebElement` | Wrapped element with auto-wait |
| `StabilizationTimeout` | Exception when UI doesn't stabilize |

## License

MIT
