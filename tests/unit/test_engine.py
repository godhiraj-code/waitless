"""Focused regression tests for stabilization engine lifecycle and timing."""

import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from waitless.config import StabilizationConfig
from waitless.engine import StabilizationEngine
from waitless.exceptions import ConfigurationError, StabilizationTimeout
from waitless.signals import StabilityStatus


class RecordingDriver:
    def __init__(self):
        self.scripts = []

    def execute_script(self, script, *args):
        self.scripts.append((script, args))
        return None


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), "1", True])
def test_per_call_timeout_is_validated_before_browser_access(timeout):
    engine = StabilizationEngine(object())

    with pytest.raises(ConfigurationError):
        engine.wait_for_stability(timeout)


def test_wait_uses_monotonic_deadline_but_epoch_time_for_signals(monkeypatch):
    engine = StabilizationEngine(object(), StabilizationConfig(poll_interval=0.1))
    engine.ensure_instrumented = Mock()
    engine._get_browser_status = Mock(return_value={})
    status = StabilityStatus(is_stable=False, signals=[], timestamp=0)
    engine.evaluator.evaluate = Mock(return_value=status)

    monotonic_values = iter([100.0, 100.0, 100.0, 101.0])
    monkeypatch.setattr("waitless.engine.time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("waitless.engine.time.time", lambda: 1_700_000_000.25)
    monkeypatch.setattr("waitless.engine.time.sleep", lambda _seconds: None)

    with pytest.raises(StabilizationTimeout) as exc_info:
        engine.wait_for_stability(timeout=1)

    assert exc_info.value.timeout == 1.0
    engine.evaluator.evaluate.assert_called_once_with({}, 1_700_000_000.25)


def test_browser_config_includes_dom_settle_time_in_milliseconds():
    engine = StabilizationEngine(
        object(), StabilizationConfig(dom_settle_time=0.275)
    )

    assert engine._browser_config()["domSettleTime"] == 275
    assert engine._browser_config()["trackLayout"] is False


def test_browser_config_only_tracks_layout_when_strict():
    engine = StabilizationEngine(
        object(), StabilizationConfig(strictness="strict", layout_stability=True)
    )

    assert engine._browser_config()["trackLayout"] is True


def test_debug_mode_only_configures_package_logger(monkeypatch):
    basic_config = Mock()
    set_level = Mock()
    monkeypatch.setattr("waitless.engine.logging.basicConfig", basic_config)
    monkeypatch.setattr("waitless.engine.logger.setLevel", set_level)

    StabilizationEngine(object(), StabilizationConfig(debug_mode=True))

    basic_config.assert_not_called()
    set_level.assert_called_once_with(logging.DEBUG)


def test_reconfigure_can_enable_package_debug_logging(monkeypatch):
    engine = StabilizationEngine(object())
    set_level = Mock()
    monkeypatch.setattr("waitless.engine.logger.setLevel", set_level)

    engine.configure(StabilizationConfig(debug_mode=True))

    set_level.assert_called_once_with(logging.DEBUG)


def test_teardown_uninstalls_adapters_destroys_instrumentation_and_resets_state():
    driver = RecordingDriver()
    engine = StabilizationEngine(driver)
    adapter = SimpleNamespace(uninstall_script="(function () { return true; })();")
    engine._instrumented = True
    engine._last_url = "https://example.test"
    engine._last_browser_state = {"pending_requests": 1}
    engine._last_blocking_factors = {"pending_requests": 1}
    engine._timeline = [{"type": "request"}]
    engine._active_adapters = [adapter]

    engine.teardown()

    assert len(driver.scripts) == 2
    assert driver.scripts[0][0].startswith("return (function")
    assert "window.__waitless__.destroy()" in driver.scripts[1][0]
    assert engine._active_adapters == []
    assert engine._instrumented is False
    assert engine._last_url is None
    assert engine._last_browser_state is None
    assert engine._last_blocking_factors == {}
    assert engine._timeline == []

    engine.teardown()
    assert len(driver.scripts) == 2
