"""Runtime browser contracts for the injected instrumentation."""

import pytest


pytest.importorskip("selenium")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from waitless.instrumentation import INSTRUMENTATION_SCRIPT


@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    browser = webdriver.Chrome(options=options)
    browser.get("data:text/html,<html><body></body></html>")
    yield browser
    browser.quit()


def inject(driver, **config):
    driver.execute_script(INSTRUMENTATION_SCRIPT, config)


def test_dom_settle_window_is_enforced_by_browser_state(driver):
    inject(driver, trackLayout=False, trackAnimations=False, domSettleTime=350)

    immediate = driver.execute_script("return window.__waitless__.getStatus()")
    assert immediate["stable"] is False
    assert immediate["dom_settle_time_ms"] == 350

    settled = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        setTimeout(() => done(window.__waitless__.getStatus()), 375);
        """
    )
    assert settled["stable"] is True
    assert settled["dom_quiet_for_ms"] >= 350

    driver.execute_script("document.body.appendChild(document.createElement('div'))")
    after_mutation = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        setTimeout(() => done(window.__waitless__.getStatus()), 0);
        """
    )
    assert after_mutation["stable"] is False
    assert after_mutation["dom_quiet_for_ms"] < 350


def test_mutation_history_is_bounded_and_pruned_while_polling(driver):
    inject(driver, trackLayout=False, trackAnimations=False)

    result = driver.execute_script(
        """
        const state = window.__waitless__;
        const now = Date.now();
        state._mutationTimestamps = Array(15000).fill(now);
        const boundedRate = state.getMutationRate();
        state._mutationTimestamps = Array(100).fill(now - 2000);
        const expiredRate = state.getStatus().mutation_rate;
        return {
            boundedRate,
            boundedLength: boundedRate,
            expiredRate,
            finalLength: state._mutationTimestamps.length
        };
        """
    )

    assert result == {
        "boundedRate": 10000,
        "boundedLength": 10000,
        "expiredRate": 0,
        "finalLength": 0,
    }


def test_layout_tracking_uses_weak_keys_and_prunes_detached_shadow_roots(driver):
    driver.execute_script(
        """
        window.__originalSetInterval = window.setInterval;
        window.setInterval = function(callback, delay) {
            window.__waitlessIntervalDelay = delay;
            return window.__originalSetInterval(callback, delay);
        };
        """
    )
    inject(driver, trackLayout=True, trackAnimations=False)

    initial_status = driver.execute_script("return window.__waitless__.getStatus()")
    assert initial_status["layout_ready"] is False

    result = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        const host = document.createElement('div');
        const root = host.attachShadow({mode: 'open'});
        const button = document.createElement('button');
        root.appendChild(button);
        document.body.appendChild(host);
        setTimeout(() => {
            const trackedBeforeRemoval = window.__waitless__._lastPositions.has(button);
            host.remove();
            setTimeout(() => done({
                delay: window.__waitlessIntervalDelay,
                weakMap: window.__waitless__._lastPositions instanceof WeakMap,
                layoutReady: window.__waitless__.getStatus().layout_ready,
                trackedBeforeRemoval,
                shadowRootsAfterRemoval: window.__waitless__._trackedShadowRoots.length
            }), 300);
        }, 300);
        """
    )

    assert result == {
        "delay": 250,
        "weakMap": True,
        "layoutReady": True,
        "trackedBeforeRemoval": True,
        "shadowRootsAfterRemoval": 0,
    }


def test_websocket_finalization_is_idempotent_and_duplicate_url_safe(driver):
    driver.execute_script(
        """
        class FakeWebSocket extends EventTarget {
            constructor(url) { super(); this.url = url; }
        }
        FakeWebSocket.CONNECTING = 0;
        FakeWebSocket.OPEN = 1;
        FakeWebSocket.CLOSING = 2;
        FakeWebSocket.CLOSED = 3;
        window.WebSocket = FakeWebSocket;
        """
    )
    inject(driver, trackLayout=False, trackAnimations=False, trackWebSocket=True)

    result = driver.execute_script(
        """
        const first = new WebSocket('wss://example.test/socket?token=one');
        const second = new WebSocket('wss://example.test/socket?token=two');
        first.dispatchEvent(new Event('error'));
        first.dispatchEvent(new Event('close'));
        return {
            active: window.__waitless__.activeWebSockets,
            details: window.__waitless__.webSocketDetails,
            uniqueIds: new Set(window.__waitless__.webSocketDetails.map(d => d.id)).size
        };
        """
    )

    assert result["active"] == 1
    assert result["uniqueIds"] == 1
    assert len(result["details"]) == 1
    assert result["details"][0]["url"] == "wss://example.test/socket"


def test_browser_url_redaction_removes_credentials_query_and_fragment(driver):
    inject(driver, trackLayout=False, trackAnimations=False)

    result = driver.execute_script(
        """
        return window.__waitless__._redactUrl(
            'https://user:password@example.test/private/path?token=secret#fragment'
        );
        """
    )

    assert result == "https://example.test/private/path"


def test_sse_reconnect_and_close_are_idempotent_and_duplicate_url_safe(driver):
    driver.execute_script(
        """
        class FakeEventSource extends EventTarget {
            constructor(url) {
                super();
                this.url = url;
                this.readyState = FakeEventSource.CONNECTING;
            }
            close() { this.readyState = FakeEventSource.CLOSED; }
        }
        FakeEventSource.CONNECTING = 0;
        FakeEventSource.OPEN = 1;
        FakeEventSource.CLOSED = 2;
        window.EventSource = FakeEventSource;
        """
    )
    inject(driver, trackLayout=False, trackAnimations=False, trackSSE=True)

    result = driver.execute_script(
        """
        const first = new EventSource('https://example.test/events?token=one');
        const second = new EventSource('https://example.test/events?token=two');
        first.dispatchEvent(new Event('error'));
        const afterReconnectError = {
            active: window.__waitless__.activeSSEConnections,
            state: window.__waitless__.sseDetails[0].state
        };
        first.close();
        first.close();
        return {
            afterReconnectError,
            active: window.__waitless__.activeSSEConnections,
            details: window.__waitless__.sseDetails
        };
        """
    )

    assert result["afterReconnectError"] == {"active": 2, "state": "reconnecting"}
    assert result["active"] == 1
    assert len(result["details"]) == 1
    assert result["details"][0]["url"] == "https://example.test/events"


def test_destroy_removes_registered_browser_event_listeners(driver):
    inject(driver, trackLayout=False, trackAnimations=True)

    result = driver.execute_script(
        """
        const state = window.__waitless__;
        const beforeDestroy = state._cleanupCallbacks.length;
        state.destroy();
        document.dispatchEvent(new Event('animationstart'));
        return {
            beforeDestroy,
            afterDestroy: state._cleanupCallbacks.length,
            activeAnimations: state.activeAnimations
        };
        """
    )

    assert result["beforeDestroy"] == 6
    assert result["afterDestroy"] == 0
    assert result["activeAnimations"] == 0


def test_nested_duplicate_src_iframes_are_tracked_by_element_and_removed(driver):
    inject(driver, trackLayout=False, trackAnimations=False, trackIframes=True)

    result = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        const wrapper = document.createElement('section');
        wrapper.innerHTML = '<div><iframe src="about:blank"></iframe>' +
                            '<iframe src="about:blank"></iframe></div>';
        document.body.appendChild(wrapper);
        setTimeout(() => {
            const before = window.__waitless__.iframeStatus.map(s => ({id: s.id, src: s.src}));
            wrapper.remove();
            setTimeout(() => done({
                before,
                afterCount: window.__waitless__.iframeStatus.length
            }), 0);
        }, 50);
        """
    )

    assert len(result["before"]) == 2
    assert len({entry["id"] for entry in result["before"]}) == 2
    assert {entry["src"] for entry in result["before"]} == {"about:blank"}
    assert result["afterCount"] == 0
