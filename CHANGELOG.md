# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] - 2026-08-30

### Fixed
- Balance XHR request accounting when a synchronous `send()` fails before `loadend`.
- Tighten README and package claims to the behavior verified by the implementation and tests.
- Propagate Python stabilization options into browser instrumentation before it initializes.
- Count individual DOM mutation records, including Shadow DOM mutations.
- Execute configured React, Angular, and Vue adapter detection/status hooks.
- Reconfigure signal evaluation when an existing wrapped driver receives new settings.
- Preserve Selenium `find_elements()` semantics and propagate stabilization failures.
- Stabilize after wrapped navigation methods and avoid retaining discarded drivers.
- Redact URL queries/fragments and align diagnostics output with its documented API.
- Install Selenium as a runtime dependency and correct misleading documentation.

## [1.0.0] - 2026-01-05

### Added
- **WebSocket/SSE Awareness** - Track WebSocket and Server-Sent Events activity with configurable quiet time
  - New options: `track_websocket`, `track_sse`, `websocket_quiet_time`
  - Idle connections are considered stable ("just chilling")
  - Activity timestamps tracked for stability decisions

- **Framework Hook Adapters** - React, Angular, and Vue framework-specific stability detection
  - `waitless.adapters` module with pluggable adapter architecture
  - React: DevTools hook integration, commit phase detection
  - Angular: NgZone stability and testability API integration
  - Vue: DevTools hook, nextTick queue monitoring
  - New option: `framework_hooks=['react', 'angular', 'vue']`

- **iframe Support** - Monitor same-origin iframes for stability
  - Automatic detection and tracking of dynamically added iframes
  - Graceful handling of cross-origin iframes (logged as inaccessible)
  - New option: `track_iframes`

- **Performance Benchmarks** - Built-in benchmark suite for measuring overhead
  - `benchmarks/overhead_test.py` for injection, poll, and stabilization timing
  - Documented performance metrics in README

- **Visual Demo** - New `examples/demo_v1_features.py` showcasing all v1.0 features

### Changed
- README updated with v1.0 features, performance section, and SPA navigation docs
- Diagnostics report now includes WebSocket/SSE connection details

---

## [0.3.2] - 2025-12-26

### Fixed
- **Stability regression for animated sites** - Reverted strict quiet-period requirement. Stabilizes correctly on pages with constant low-rate mutations (e.g., particle effects).
- **Unicode compatibility** - Replaced non-ASCII markers in diagnostics and demo scripts to prevent `UnicodeEncodeError` on Windows consoles.
- **CI Artifacts** - Fixed matrix job conflicts by using unique artifact names for each Python version.
- **CI Pipeline** - Switched to official `setup-chrome` action for more reliable browser testing on Ubuntu.

---

## [0.3.1] - 2025-12-26

### Added
- **Shadow DOM support** - `MutationObserver` now recursively tracks changes inside shadow roots.
- **Improved stability detection** - Fixed a bug where quiet time was ignored when mutation rate was low.
- **Shadow DOM integration tests** - New test fixture and integration tests for shadow DOM scenarios.

---

## [0.3.0] - 2025-12-25

### Added
- **Input validation** - `stabilize()` now raises clear `TypeError` when invalid drivers are passed
- **Comprehensive test coverage** - New tests for `diagnostics.py` and `instrumentation.py` modules
- **Dynamic site support** - Demo updated with `relaxed` mode for highly animated websites

### Changed
- **Exception handling** - Replaced broad `except Exception` with specific Selenium exceptions (`WebDriverException`, `JavascriptException`, `NoSuchWindowException`)
- **Debug logging** - Exception handlers now log details when debug mode is enabled
- **Homepage URL** - Updated to `www.dhirajdas.dev`

### Fixed
- **Integration tests** - Removed all `time.sleep()` calls, now using proper waitless mechanisms
- **Config test** - Fixed `network_idle_threshold` assertion to match actual default of `2`

---

## [0.2.0] - 2025-12-24

### Added
- **Mutation rate detection** - Uses 50 mutations/sec threshold instead of absolute DOM silence
- **Auto-retry find_element** - Elements found automatically when they appear, no `WebDriverWait` needed
- **Non-blocking animations** - CSS animations don't block in `normal` mode
- **Enhanced diagnostics** - Shows `mutation_rate`, `pending_requests`, `active_animations`

### Changed
- Default `network_idle_threshold` set to `2` to allow background traffic

---

## [0.1.0] - 2025-12-23

### Added
- Initial release
- Core stabilization engine with JavaScript instrumentation
- `stabilize()` / `unstabilize()` / `wait_for_stability()` API
- `StabilizationConfig` with configurable thresholds
- Strictness levels: `strict`, `normal`, `relaxed`
- Factory methods: `StabilizationConfig.strict()`, `.relaxed()`, `.ci()`
- Diagnostic reporting with `waitless doctor` CLI
- `StabilizedWebDriver` and `StabilizedWebElement` wrappers
