"""
Visual Demo: Waitless v1.0 Features

This demo showcases the new v1.0 features:
- WebSocket/SSE tracking
- Framework adapters (React detection)
- iframe monitoring

Run with: python examples/demo_v1_features.py
"""

import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# Our library
from waitless import stabilize, StabilizationConfig


# Test page HTML with WebSocket simulation
TEST_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Waitless v1.0 Demo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh; color: #fff; padding: 40px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { font-size: 2.5rem; margin-bottom: 10px; 
             background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%);
             -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .subtitle { color: #888; margin-bottom: 30px; }
        .card { 
            background: rgba(255,255,255,0.1); border-radius: 16px;
            padding: 24px; margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 { font-size: 1.2rem; margin-bottom: 15px; color: #4facfe; }
        .status { display: flex; align-items: center; gap: 10px; margin: 10px 0; }
        .dot { width: 12px; height: 12px; border-radius: 50%; }
        .dot.green { background: #00f5a0; box-shadow: 0 0 10px #00f5a0; }
        .dot.yellow { background: #ffc107; box-shadow: 0 0 10px #ffc107; }
        .dot.red { background: #ff4757; box-shadow: 0 0 10px #ff4757; }
        .dot.gray { background: #444; }
        button {
            background: linear-gradient(to right, #4facfe, #00f2fe);
            border: none; padding: 12px 24px; border-radius: 8px;
            color: #000; font-weight: bold; cursor: pointer;
            margin-right: 10px; margin-bottom: 10px;
            transition: transform 0.2s;
        }
        button:hover { transform: scale(1.05); }
        .log { 
            background: #0a0a14; border-radius: 8px; padding: 15px;
            font-family: monospace; font-size: 12px; max-height: 200px;
            overflow-y: auto; color: #4facfe;
        }
        .log-entry { margin: 5px 0; opacity: 0.8; }
        iframe { border: 2px solid rgba(255,255,255,0.2); border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Waitless v1.0 Demo</h1>
        <p class="subtitle">Testing WebSocket, SSE, and iframe tracking</p>
        
        <div class="card">
            <h2>WebSocket Simulation</h2>
            <div class="status">
                <div class="dot gray" id="ws-status"></div>
                <span id="ws-label">Not connected</span>
            </div>
            <button onclick="simulateWebSocket()">Simulate WebSocket</button>
            <button onclick="sendWSMessage()">Send Message</button>
        </div>
        
        <div class="card">
            <h2>DOM Activity</h2>
            <div id="activity-container">
                <div class="status">
                    <div class="dot gray" id="dom-status"></div>
                    <span id="dom-label">Idle</span>
                </div>
            </div>
            <button onclick="simulateDOMUpdates()">Trigger DOM Updates</button>
            <button onclick="simulateNetworkCall()">Make API Call</button>
        </div>
        
        <div class="card">
            <h2>iframe Test</h2>
            <iframe id="test-iframe" width="100%" height="100" srcdoc="
                <html><body style='background:#1a1a2e;color:#fff;padding:20px;font-family:sans-serif;'>
                    <div id='iframe-content'>iframe content loading...</div>
                    <script>
                        setTimeout(function() {
                            document.getElementById('iframe-content').textContent = 'iframe loaded at ' + new Date().toLocaleTimeString();
                        }, 500);
                    </script>
                </body></html>
            "></iframe>
        </div>
        
        <div class="card">
            <h2>Activity Log</h2>
            <div class="log" id="log"></div>
        </div>
    </div>
    
    <script>
        var wsConnected = false;
        var lastWSActivity = 0;
        
        function log(message) {
            var logEl = document.getElementById('log');
            var entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.textContent = '[' + new Date().toLocaleTimeString() + '] ' + message;
            logEl.insertBefore(entry, logEl.firstChild);
        }
        
        function simulateWebSocket() {
            var statusEl = document.getElementById('ws-status');
            var labelEl = document.getElementById('ws-label');
            
            statusEl.className = 'dot yellow';
            labelEl.textContent = 'Connecting...';
            log('WebSocket connecting...');
            
            // Simulate connection delay
            setTimeout(function() {
                wsConnected = true;
                lastWSActivity = Date.now();
                statusEl.className = 'dot green';
                labelEl.textContent = 'Connected';
                log('WebSocket connected!');
            }, 800);
        }
        
        function sendWSMessage() {
            if (!wsConnected) {
                log('WebSocket not connected!');
                return;
            }
            
            var statusEl = document.getElementById('ws-status');
            statusEl.className = 'dot yellow';
            lastWSActivity = Date.now();
            log('Sending WebSocket message...');
            
            setTimeout(function() {
                statusEl.className = 'dot green';
                log('Message received: "Echo response"');
            }, 200);
        }
        
        function simulateDOMUpdates() {
            var container = document.getElementById('activity-container');
            var statusEl = document.getElementById('dom-status');
            var labelEl = document.getElementById('dom-label');
            
            statusEl.className = 'dot yellow';
            labelEl.textContent = 'Updating...';
            log('DOM updates started');
            
            var count = 0;
            var interval = setInterval(function() {
                count++;
                var item = document.createElement('div');
                item.className = 'status';
                item.innerHTML = '<div class="dot green"></div><span>Update #' + count + '</span>';
                container.appendChild(item);
                
                if (count >= 5) {
                    clearInterval(interval);
                    statusEl.className = 'dot green';
                    labelEl.textContent = 'Complete';
                    log('DOM updates complete');
                }
            }, 200);
        }
        
        function simulateNetworkCall() {
            var statusEl = document.getElementById('dom-status');
            var labelEl = document.getElementById('dom-label');
            
            statusEl.className = 'dot yellow';
            labelEl.textContent = 'Fetching...';
            log('Network request started');
            
            fetch('https://jsonplaceholder.typicode.com/posts/1')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    statusEl.className = 'dot green';
                    labelEl.textContent = 'Complete';
                    log('Network response: ' + data.title.substring(0, 30) + '...');
                })
                .catch(function(e) {
                    statusEl.className = 'dot red';
                    labelEl.textContent = 'Error';
                    log('Network error: ' + e.message);
                });
        }
        
        // Initial log
        log('Page loaded. Ready for testing!');
    </script>
</body>
</html>
"""


def run_demo():
    """Run the visual demo of Waitless v1.0 features."""
    print("\n" + "="*60)
    print("  WAITLESS v1.0 VISUAL DEMO")
    print("="*60)
    
    # Create test page
    test_file = os.path.join(os.path.dirname(__file__), 'demo_v1_test_page.html')
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(TEST_PAGE_HTML)
    print(f"\n[+] Created test page: {test_file}")
    
    # Setup Chrome
    options = Options()
    # Comment next line to see the browser
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1200,900')
    
    print("[+] Launching Chrome browser...")
    driver = webdriver.Chrome(options=options)
    
    try:
        # Configure Waitless with v1.0 features
        config = StabilizationConfig(
            timeout=15,
            track_websocket=True,
            track_sse=True,
            track_iframes=True,
            debug_mode=True,
        )
        
        # Wrap driver with Waitless
        driver = stabilize(driver, config=config)
        print("[+] Waitless v1.0 instrumentation active")
        print(f"    - WebSocket tracking: {config.track_websocket}")
        print(f"    - SSE tracking: {config.track_sse}")
        print(f"    - iframe tracking: {config.track_iframes}")
        
        # Navigate to test page
        file_url = f"file:///{test_file.replace(os.sep, '/')}"
        print(f"\n[+] Opening: {file_url}")
        driver.get(file_url)
        print("[+] Page loaded and stabilized!")
        
        # Simulate some activity
        print("\n[*] Simulating WebSocket connection...")
        ws_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Simulate WebSocket')]")
        ws_btn.click()
        time.sleep(1)
        
        print("[*] Simulating DOM updates...")
        dom_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Trigger DOM')]")
        dom_btn.click()
        time.sleep(2)
        
        print("[*] Simulating network call...")
        net_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Make API')]")
        net_btn.click()
        time.sleep(2)
        
        # Take screenshot
        screenshot_path = os.path.join(os.path.dirname(__file__), 'demo_v1_screenshot.png')
        driver.save_screenshot(screenshot_path)
        print(f"\n[+] Screenshot saved: {screenshot_path}")
        
        # ===== SHOW DIAGNOSTICS REPORT =====
        print("\n" + "="*60)
        print("  WAITLESS DOCTOR - DIAGNOSTICS REPORT")
        print("="*60 + "\n")
        
        from waitless import get_diagnostics
        from waitless.diagnostics import DiagnosticReport
        
        # Get diagnostics from the driver
        try:
            diagnostics = get_diagnostics(driver)
            report = DiagnosticReport(diagnostics)
            print(report.generate_text_report())
        except Exception as e:
            print(f"[!] Could not get diagnostics: {e}")
            # Fallback: get raw status from browser
            try:
                status = driver.execute_script("return window.__waitless__ ? window.__waitless__.getStatus() : null;")
                if status:
                    print("\n[+] Raw Browser State:")
                    print(f"    - Pending requests: {status.get('pending_requests', 'N/A')}")
                    print(f"    - Mutation rate: {status.get('mutation_rate', 'N/A')}/sec")
                    print(f"    - Active animations: {status.get('active_animations', 'N/A')}")
                    print(f"    - Active WebSockets: {status.get('active_websockets', 'N/A')}")
                    print(f"    - Active SSE: {status.get('active_sse', 'N/A')}")
                    print(f"    - Layout shifting: {status.get('layout_shifting', 'N/A')}")
                    
                    ws_details = status.get('websocket_details', [])
                    if ws_details:
                        print(f"\n    WebSocket connections ({len(ws_details)}):")
                        for ws in ws_details:
                            print(f"      - {ws.get('state', '?')} {ws.get('url', 'unknown')}")
                    
                    iframe_status = status.get('iframe_status', [])
                    if iframe_status:
                        print(f"\n    iframes ({len(iframe_status)}):")
                        for iframe in iframe_status:
                            print(f"      - {iframe.get('src', 'inline')} (loaded: {iframe.get('loaded', '?')})")
            except Exception as e2:
                print(f"[!] Could not get raw status: {e2}")
        
        print("\n" + "="*60)
        print("  DEMO COMPLETE!")
        print("="*60)
        print("\nThe browser will stay open for 10 seconds so you can see it...")
        print("Press Ctrl+C to exit early.\n")
        
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            pass
        
    finally:
        driver.quit()
        print("[+] Browser closed.")


if __name__ == '__main__':
    run_demo()

