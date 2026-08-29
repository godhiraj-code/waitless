# Waitless

[![CI](https://github.com/godhiraj-code/waitless/actions/workflows/ci.yml/badge.svg)](https://github.com/godhiraj-code/waitless/actions/workflows/ci.yml)

**Automatic UI stabilization for Selenium**

Reduce explicit waits and sleeps by automatically evaluating multiple UI stability signals.



## Installation

```bash
pip install waitless
```

## Quick Start

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from waitless import stabilize

driver = webdriver.Chrome()
driver = stabilize(driver)

# Navigation, lookups, and common element actions now wait for stability.
driver.get(
    "data:text/html,<input id='username'><button id='login-button'>Log in</button>"
)
driver.find_element(By.ID, "username").send_keys("user")
driver.find_element(By.ID, "login-button").click()
driver.quit()
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
| `WebDriverWait` | Requires an explicit condition at each synchronization point |
| Retries | Masks the real problem, adds flakiness |

### The Waitless Solution

Waitless evaluates page-level stability signals:

- DOM mutation activity (MutationObserver, including **Shadow DOM**)
- Pending network requests (XHR/fetch interception after instrumentation is installed)
- CSS animations and transitions
- Layout stability for interactive elements
- WebSocket/SSE activity (opt-in)
- Framework hooks (React/Angular/Vue, opt-in)
- Same-origin iframe load readiness (opt-in; not full child-frame signal injection)

Before supported interactions, Waitless polls until the enabled mandatory signals
meet their configured thresholds.

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
    print_report(diagnostics)  # Print detailed report
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

If known background traffic exceeds the default, raise the threshold carefully:
```python
config = StabilizationConfig(network_idle_threshold=3)
```

### Wrapped Elements

The stabilized driver returns wrapped elements that auto-wait before `click()`,
`send_keys()`, `submit()`, and `clear()`. They behave like WebElements but:

- `isinstance(element, WebElement)` returns `False`
- Use `.unwrap()` to get the original element if needed

```python
element = driver.find_element(By.ID, "button")
original = element.unwrap()  # Gets the real WebElement
```

## Optional Signals

- **WebSocket/SSE Awareness** - Track WebSocket and Server-Sent Events activity
- **Framework Adapters** - React, Angular, Vue hooks for framework-specific settling
- **iframe Support** - Monitor same-origin iframes
- **Performance benchmarks** - Run the repository benchmark against your environment

```python
config = StabilizationConfig(
    track_websocket=True,         # WebSocket monitoring
    track_sse=True,               # SSE monitoring
    framework_hooks=['react'],    # React adapter
    track_iframes=True,           # iframe monitoring
)
```

## Performance

| Metric | Typical Value |
|--------|---------------|
| Instrumentation injection | Environment-dependent; from a repository checkout, run `python benchmarks/overhead_test.py` |
| Per-poll overhead | Environment-dependent; run the repository benchmark |
| Poll interval (default) | 50ms |
| Stabilization time | Depends on page activity, thresholds, and environment |

### Navigation Handling

Wrapped `get()`, `refresh()`, `back()`, and `forward()` wait after Selenium's
synchronous navigation call returns. For SPA route changes initiated by page
JavaScript, Waitless validates/re-injects instrumentation on the next wait:

1. Checks `__waitless__.isAlive()` before each wait
2. Detects URL changes via `driver.current_url`
3. Re-injects if instrumentation is missing

This does not observe routes continuously, and cross-origin iframe internals remain
outside the browser same-origin boundary.

Because instrumentation is installed after Selenium's synchronous navigation call
returns, requests that start and finish during navigation are not observed. Requests
started after instrumentation is installed are tracked.

`find_elements()` keeps Selenium's immediate-empty lookup semantics: after the
page-stability wait, it performs one lookup and returns `[]` when there are no matches.
By contrast, `find_element()` retries `NoSuchElementException` until the configured
timeout after the page-stability wait.

## Current Limitations

- **Selenium only** - No Playwright integration
- **Sync only** - No async/await support yet
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
