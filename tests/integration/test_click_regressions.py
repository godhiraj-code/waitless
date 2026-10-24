"""Real-browser regressions for delayed list redraws and loading overlays."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import time

import pytest
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException, StaleElementReferenceException, TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from waitless import StabilizationConfig, stabilize
from waitless.selenium_integration import FINGERPRINT_SCRIPT


PAGE = rb"""<!doctype html>
<html><body><div id="list"></div><output id="result"></output>
<script>
function render(generation) {
    document.querySelector('#list').outerHTML =
        '<div id="list"><button id="action" data-generation="' + generation +
        '" onclick="document.querySelector(\'#result\').textContent=\'clicked\'">' +
        'Click</button></div>';
}
function redraw() {
    return fetch('/delay').then(response => response.text()).then(() => render('fresh'));
}
function startList() {
    setTimeout(() => { render('initial'); redraw(); }, 150);
}
function startOverlay() {
    render('initial');
    document.querySelector('#action').disabled = true;
    const overlay = document.createElement('div');
    overlay.id = 'overlay';
    overlay.style = 'position:fixed;inset:0;z-index:10;background:#ddd';
    document.body.appendChild(overlay);
    fetch('/slow').then(response => response.text()).then(() => {
        overlay.remove();
        document.querySelector('#action').disabled = false;
    });
}
function renderFruits(reverse) {
    const fruits = reverse ? ['banana', 'apple'] : ['apple', 'banana'];
    document.querySelector('#list').innerHTML = fruits.map(fruit =>
        '<button class="fruit" data-testid="' + fruit + '" onclick="' +
        'document.querySelector(\'#result\').textContent=\'' + fruit + '\'">' +
        fruit + '</button>').join('');
}
function renderDeleteRows(reverse) {
    const fruits = reverse ? ['banana', 'apple'] : ['apple', 'banana'];
    document.querySelector('#list').innerHTML = fruits.map(fruit =>
        '<div class="row"><span>' + fruit + '</span> <button class="delete" onclick="' +
        'document.querySelector(\'#result\').textContent=\'' + fruit + '\';' +
        'this.parentElement.remove()">Delete</button></div>').join('');
}
</script></body></html>"""


@pytest.fixture(scope="module")
def local_page():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/delay', '/slow', '/empty'):
                time.sleep({'/delay': 0.5, '/slow': 1.5, '/empty': 0.4}[self.path])
                body = b'ready'
            else:
                body = PAGE
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    browser = webdriver.Chrome(options=options)
    try:
        yield browser
    finally:
        browser.quit()


@pytest.mark.parametrize('strict', [False, True])
def test_find_returns_fresh_element_after_delayed_list_redraw(driver, local_page, strict):
    config = StabilizationConfig.strict() if strict else StabilizationConfig()
    wrapped = stabilize(driver, config=config)
    wrapped.get(local_page)
    driver.execute_script('startList()')

    button = wrapped.find_element(By.ID, 'action')

    assert button.get_attribute('data-generation') == 'fresh'
    button.click()
    assert driver.find_element(By.ID, 'result').text == 'clicked'


def test_click_recovers_when_list_is_replaced_after_find(driver, local_page):
    wrapped = stabilize(driver, config=StabilizationConfig.strict())
    wrapped.get(local_page)
    driver.execute_script("render('initial')")
    button = wrapped.find_element(By.ID, 'action')
    original_id = button.unwrap().id
    driver.execute_script('redraw()')

    button.click()

    assert button.unwrap().id != original_id
    assert button.get_attribute('data-generation') == 'fresh'
    assert driver.find_element(By.ID, 'result').text == 'clicked'


@pytest.mark.parametrize('mode', ['default', 'strict', 'background'])
def test_click_waits_for_disabled_button_and_delayed_fetch_overlay(driver, local_page, mode):
    config = StabilizationConfig.strict() if mode == 'strict' else StabilizationConfig()
    if mode == 'background':
        # Even when a caller permits pending requests, click must wait for enabled.
        config = config.with_overrides(network_idle_threshold=2)
    wrapped = stabilize(driver, config=config)
    wrapped.get(local_page)
    driver.execute_script('startOverlay()')

    wrapped.find_element(By.ID, 'action').click()

    assert driver.find_element(By.ID, 'result').text == 'clicked'
    assert driver.find_elements(By.ID, 'overlay') == []
    assert driver.execute_script('return window.__waitless__.pendingRequests') == 0


def test_stale_retry_refuses_reordered_list_element(driver, local_page):
    wrapped = stabilize(driver)
    wrapped.get(local_page)
    driver.execute_script('renderFruits(false)')
    apple = wrapped.find_element(By.CSS_SELECTOR, '.fruit')
    assert apple.text == 'apple'
    driver.execute_script('renderFruits(true)')

    with pytest.raises(StaleElementReferenceException, match='Element changed; Waitless refused'):
        apple.click()

    assert driver.find_element(By.ID, 'result').text == ''


@pytest.mark.parametrize('pending_fetch', [True, False])
def test_stale_retry_waits_through_transient_empty_list(driver, local_page, monkeypatch, pending_fetch):
    wrapped = stabilize(driver, config=StabilizationConfig.strict())
    wrapped.get(local_page)
    driver.execute_script("render('initial')")
    button = wrapped.find_element(By.ID, 'action')
    original_enabled = button.unwrap().is_enabled

    def redraw_during_enabled_check():
        # Deterministically redraw after click's initial stability wait.
        driver.execute_script("""
            document.querySelector('#list').innerHTML = '';
            if (arguments[0]) {
                fetch('/empty').then(r => r.text()).then(() => render('fresh'));
            } else {
                setTimeout(() => render('fresh'), 400);
            }
        """, pending_fetch)
        return original_enabled()  # Real WebDriver stale-reference failure.

    monkeypatch.setattr(button.unwrap(), 'is_enabled', redraw_during_enabled_check)
    button.click()

    assert button.get_attribute('data-generation') == 'fresh'
    assert driver.find_element(By.ID, 'result').text == 'clicked'


def test_disabled_click_reports_element_and_respects_total_timeout(driver, local_page):
    wrapped = stabilize(driver, config=StabilizationConfig(timeout=2.0))
    wrapped.get(local_page)
    driver.execute_script("render('initial'); document.querySelector('#action').disabled = true")
    button = wrapped.find_element(By.ID, 'action')
    # Network settling consumes most of the same two-second click budget.
    driver.execute_script("fetch('/slow')")
    started = time.monotonic()

    with pytest.raises(TimeoutException) as caught:
        button.click()

    elapsed = time.monotonic() - started
    assert 1.9 <= elapsed <= 2.5
    assert "Element <button> 'Click' was not enabled after 2.0s" in str(caught.value)
    assert driver.find_element(By.ID, 'result').text == ''


def test_find_missing_element_respects_total_timeout(driver, local_page):
    wrapped = stabilize(driver, config=StabilizationConfig(timeout=2.0))
    wrapped.get(local_page)
    driver.execute_script("fetch('/slow')")
    started = time.monotonic()

    with pytest.raises(NoSuchElementException):
        wrapped.find_element(By.ID, 'absent')

    assert 1.9 <= time.monotonic() - started <= 2.5


@pytest.mark.parametrize('reorder', [True, False])
def test_delete_buttons_use_row_context_on_stale_retry(driver, local_page, reorder):
    wrapped = stabilize(driver)
    wrapped.get(local_page)
    driver.execute_script('renderDeleteRows(false)')
    button = wrapped.find_element(By.CSS_SELECTOR, '.delete')
    driver.execute_script('renderDeleteRows(arguments[0])', reorder)

    if reorder:
        with pytest.raises(StaleElementReferenceException, match='Element changed'):
            button.click()
        assert driver.find_element(By.ID, 'result').text == ''
        assert len(driver.find_elements(By.CSS_SELECTOR, '.row')) == 2
    else:
        button.click()
        assert driver.find_element(By.ID, 'result').text == 'apple'
        assert len(driver.find_elements(By.CSS_SELECTOR, '.row')) == 1


def test_permanently_disappeared_button_reports_missing(driver, local_page):
    wrapped = stabilize(driver, config=StabilizationConfig(timeout=2.0))
    wrapped.get(local_page)
    driver.execute_script("render('initial')")
    button = wrapped.find_element(By.ID, 'action')
    driver.execute_script("document.querySelector('#list').innerHTML = ''")

    with pytest.raises(NoSuchElementException, match='is no longer on the page') as caught:
        button.click()

    assert 'not enabled' not in str(caught.value)
    assert driver.find_element(By.ID, 'result').text == ''


def test_fingerprint_snapshot_caps_text_in_single_browser_read(driver, local_page, monkeypatch):
    wrapped = stabilize(driver)
    wrapped.get(local_page)
    driver.execute_script("""
        document.querySelector('#list').innerHTML = '<div id="large"></div>';
        document.querySelector('#large').textContent = '  ' + 'X'.repeat(2000) + '  ';
    """)
    original_script = driver.execute_script
    snapshots = []

    def record_snapshot(script, *args):
        result = original_script(script, *args)
        if script == FINGERPRINT_SCRIPT:
            snapshots.append(result)
        return result

    monkeypatch.setattr(driver, 'execute_script', record_snapshot)
    element = wrapped.find_element(By.ID, 'large')

    assert len(snapshots) == 1
    assert snapshots[0][1] == 'X' * 200
    assert snapshots[0][4] == 'X' * 200
    assert element._fingerprint[3] == 0


def test_find_recovers_when_element_goes_stale_during_snapshot(driver, local_page, monkeypatch):
    wrapped = stabilize(driver)
    wrapped.get(local_page)
    driver.execute_script("render('initial')")
    original_script = driver.execute_script
    reads = []

    def replace_during_snapshot(script, *args):
        if script == FINGERPRINT_SCRIPT:
            reads.append(True)
            if len(reads) == 1:
                original_script("render('fresh')")
        return original_script(script, *args)

    monkeypatch.setattr(driver, 'execute_script', replace_during_snapshot)
    button = wrapped.find_element(By.ID, 'action')
    button.click()

    assert len(reads) == 2
    assert button.get_attribute('data-generation') == 'fresh'
    assert driver.find_element(By.ID, 'result').text == 'clicked'
