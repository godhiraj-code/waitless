"""
JavaScript instrumentation for browser-side stability monitoring.
"""

INSTRUMENTATION_SCRIPT = """
(function() {
    // Avoid re-initialization
    if (window.__waitless__ && window.__waitless__._initialized) {
        return window.__waitless__;
    }
    
    window.__waitless__ = {
        _initialized: true,
        _version: '1.0.0',
        
        // State tracking
        pendingRequests: 0,
        lastMutationTime: Date.now(),
        activeAnimations: 0,
        activeTransitions: 0,
        layoutShifting: false,
        
        // WebSocket/SSE tracking
        activeWebSockets: 0,
        activeSSEConnections: 0,
        lastWebSocketActivity: 0,
        lastSSEActivity: 0,
        webSocketDetails: [],
        sseDetails: [],
        
        // iframe tracking
        iframeStatus: [],  // Status from child iframes
        
        // Timeline for diagnostics (circular buffer)
        timeline: [],
        _maxTimelineEntries: 100,
        
        // Request tracking for diagnostics
        pendingRequestDetails: [],
        
        // Configuration (updated from Python)
        config: {
            trackLayout: true,
            trackAnimations: true,
            trackWebSocket: false,
            trackSSE: false,
            webSocketQuietTime: 500,  // ms of silence for stability
            trackIframes: false,
        },
        
        // Lifecycle
        _observers: [],
        _originalFetch: null,
        _originalXHROpen: null,
        _originalXHRSend: null,
        _originalWebSocket: null,
        _originalEventSource: null,
        
        // ===== INITIALIZATION =====
        
        init: function() {
            this._setupMutationObserver();
            this._setupNetworkInterceptors();
            this._setupAnimationTracking();
            if (this.config.trackLayout) {
                this._setupLayoutTracking();
            }
            if (this.config.trackWebSocket) {
                this._setupWebSocketTracking();
            }
            if (this.config.trackSSE) {
                this._setupSSETracking();
            }
            if (this.config.trackIframes) {
                this._setupIframeTracking();
            }
            this._log('Waitless instrumentation initialized');
            return this;
        },
        
        // ===== LOGGING =====
        
        _log: function(message, data) {
            var entry = {
                time: Date.now(),
                message: message,
                data: data || null
            };
            this.timeline.push(entry);
            if (this.timeline.length > this._maxTimelineEntries) {
                this.timeline.shift();
            }
        },
        
        // ===== MUTATION OBSERVER =====
        
        // Rolling window for mutation rate calculation
        _mutationTimestamps: [],
        _mutationWindowMs: 1000,  // 1 second window for rate calculation
        _observedShadowRoots: new WeakSet(),
        
        _setupMutationObserver: function() {
            var self = this;
            var observer = new MutationObserver(function(mutations) {
                var now = Date.now();
                self.lastMutationTime = now;
                
                // Add to rolling window
                self._mutationTimestamps.push(now);
                
                // Remove old timestamps outside the window
                var cutoff = now - self._mutationWindowMs;
                while (self._mutationTimestamps.length > 0 && self._mutationTimestamps[0] < cutoff) {
                    self._mutationTimestamps.shift();
                }
                
                // Check for new shadow roots in added nodes
                mutations.forEach(function(mutation) {
                    mutation.addedNodes.forEach(function(node) {
                        if (node.nodeType === 1) { // Element node
                            self._observeShadowRoots(node);
                        }
                    });
                });
                
                self._log('DOM mutation', { count: mutations.length, rate: self.getMutationRate() });
            });
            
            var config = {
                childList: true,
                subtree: true,
                attributes: true,
                characterData: true
            };
            
            observer.observe(document.documentElement || document.body, config);
            this._observers.push(observer);
            
            // Initial scan for shadow roots
            this._observeShadowRoots(document);
        },
        
        _observeShadowRoots: function(root) {
            var self = this;
            
            // Function to recursively find and observe shadow roots
            var walk = function(node) {
                if (node.shadowRoot && !self._observedShadowRoots.has(node.shadowRoot)) {
                    self._observedShadowRoots.add(node.shadowRoot);
                    
                    var observer = new MutationObserver(function(mutations) {
                        var now = Date.now();
                        self.lastMutationTime = now;
                        self._mutationTimestamps.push(now);
                        self._log('Shadow DOM mutation', { count: mutations.length });
                        
                        // Scan new nodes in shadow DOM for nested shadow roots
                        mutations.forEach(function(mutation) {
                            mutation.addedNodes.forEach(function(newNode) {
                                if (newNode.nodeType === 1) walk(newNode);
                            });
                        });
                    });
                    
                    observer.observe(node.shadowRoot, {
                        childList: true,
                        subtree: true,
                        attributes: true,
                        characterData: true
                    });
                    
                    self._observers.push(observer);
                    self._log('Observing shadow root', { host: node.tagName });
                    
                    // Recurse into the shadow root
                    walk(node.shadowRoot);
                }
                
                // Traverse children
                var child = node.firstElementChild;
                while (child) {
                    walk(child);
                    child = child.nextElementSibling;
                }
            };
            
            walk(root);
        },
        
        // Calculate mutations per second from rolling window
        getMutationRate: function() {
            var now = Date.now();
            var cutoff = now - this._mutationWindowMs;
            
            // Count mutations in the last second
            var count = 0;
            for (var i = 0; i < this._mutationTimestamps.length; i++) {
                if (this._mutationTimestamps[i] > cutoff) {
                    count++;
                }
            }
            
            // Return rate per second
            return count;
        },
        
        // ===== NETWORK INTERCEPTORS =====
        
        _setupNetworkInterceptors: function() {
            var self = this;
            
            // Intercept fetch
            this._originalFetch = window.fetch;
            window.fetch = function(input, init) {
                var url = typeof input === 'string' ? input : input.url;
                self._requestStarted(url, 'fetch');
                
                return self._originalFetch.apply(window, arguments)
                    .then(function(response) {
                        self._requestEnded(url, 'fetch', response.status);
                        return response;
                    })
                    .catch(function(error) {
                        self._requestEnded(url, 'fetch', 'error');
                        throw error;
                    });
            };
            
            // Intercept XMLHttpRequest
            this._originalXHROpen = XMLHttpRequest.prototype.open;
            this._originalXHRSend = XMLHttpRequest.prototype.send;
            
            XMLHttpRequest.prototype.open = function(method, url) {
                this._waitless_url = url;
                this._waitless_method = method;
                return self._originalXHROpen.apply(this, arguments);
            };
            
            XMLHttpRequest.prototype.send = function() {
                var xhr = this;
                var url = xhr._waitless_url || 'unknown';
                
                self._requestStarted(url, 'xhr');
                
                xhr.addEventListener('loadend', function() {
                    self._requestEnded(url, 'xhr', xhr.status);
                });
                
                return self._originalXHRSend.apply(this, arguments);
            };
        },
        
        _requestStarted: function(url, type) {
            this.pendingRequests++;
            this.pendingRequestDetails.push({
                url: url,
                type: type,
                startTime: Date.now()
            });
            this._log('Request started', { url: url, type: type, pending: this.pendingRequests });
        },
        
        _requestEnded: function(url, type, status) {
            this.pendingRequests = Math.max(0, this.pendingRequests - 1);
            
            // Remove from pending details
            var idx = this.pendingRequestDetails.findIndex(function(r) {
                return r.url === url && r.type === type;
            });
            if (idx > -1) {
                this.pendingRequestDetails.splice(idx, 1);
            }
            
            this._log('Request ended', { url: url, type: type, status: status, pending: this.pendingRequests });
        },
        
        // ===== ANIMATION TRACKING =====
        
        _setupAnimationTracking: function() {
            var self = this;
            
            // CSS Animations
            document.addEventListener('animationstart', function(e) {
                self.activeAnimations++;
                self._log('Animation started', { name: e.animationName });
            }, true);
            
            document.addEventListener('animationend', function(e) {
                self.activeAnimations = Math.max(0, self.activeAnimations - 1);
                self._log('Animation ended', { name: e.animationName });
            }, true);
            
            document.addEventListener('animationcancel', function(e) {
                self.activeAnimations = Math.max(0, self.activeAnimations - 1);
                self._log('Animation cancelled', { name: e.animationName });
            }, true);
            
            // CSS Transitions
            document.addEventListener('transitionstart', function(e) {
                self.activeTransitions++;
                self._log('Transition started', { property: e.propertyName });
            }, true);
            
            document.addEventListener('transitionend', function(e) {
                self.activeTransitions = Math.max(0, self.activeTransitions - 1);
                self._log('Transition ended', { property: e.propertyName });
            }, true);
            
            document.addEventListener('transitioncancel', function(e) {
                self.activeTransitions = Math.max(0, self.activeTransitions - 1);
                self._log('Transition cancelled', { property: e.propertyName });
            }, true);
        },
        
        // ===== LAYOUT TRACKING =====
        
        _setupLayoutTracking: function() {
            var self = this;
            this._lastPositions = new Map();
            this._layoutCheckInterval = null;
            
            // Periodic layout stability check
            this._layoutCheckInterval = setInterval(function() {
                self._checkLayoutStability();
            }, 50);
        },
        
        _checkLayoutStability: function() {
            // Track key interactive elements, including those in shadow DOM
            var elements = [];
            
            var collectElements = function(root) {
                var found = root.querySelectorAll('button, a, input, [onclick], [role="button"]');
                for (var i = 0; i < found.length; i++) {
                    elements.push(found[i]);
                }
                
                // Recursively check shadow roots
                var all = root.querySelectorAll('*');
                for (var j = 0; j < all.length; j++) {
                    if (all[j].shadowRoot) {
                        collectElements(all[j].shadowRoot);
                    }
                }
            };
            
            collectElements(document);
            
            var isShifting = false;
            var self = this;
            
            elements.forEach(function(el) {
                var rect = el.getBoundingClientRect();
                var key = el.id || el.className || el.tagName;
                var lastPos = self._lastPositions.get(el);
                
                if (lastPos) {
                    var dx = Math.abs(rect.left - lastPos.left);
                    var dy = Math.abs(rect.top - lastPos.top);
                    if (dx > 1 || dy > 1) {
                        isShifting = true;
                    }
                }
                
                self._lastPositions.set(el, {
                    left: rect.left,
                    top: rect.top,
                    width: rect.width,
                    height: rect.height
                });
            });
            
            if (this.layoutShifting !== isShifting) {
                this.layoutShifting = isShifting;
                this._log('Layout stability changed', { shifting: isShifting });
            }
        },
        
        // ===== WEBSOCKET TRACKING =====
        
        _setupWebSocketTracking: function() {
            var self = this;
            this._originalWebSocket = window.WebSocket;
            
            window.WebSocket = function(url, protocols) {
                var ws = protocols 
                    ? new self._originalWebSocket(url, protocols)
                    : new self._originalWebSocket(url);
                
                self.activeWebSockets++;
                self.webSocketDetails.push({
                    url: url,
                    openTime: Date.now(),
                    state: 'connecting'
                });
                self._log('WebSocket connecting', { url: url });
                
                ws.addEventListener('open', function() {
                    self.lastWebSocketActivity = Date.now();
                    var detail = self.webSocketDetails.find(function(d) { return d.url === url; });
                    if (detail) detail.state = 'open';
                    self._log('WebSocket opened', { url: url });
                });
                
                ws.addEventListener('message', function(e) {
                    self.lastWebSocketActivity = Date.now();
                    self._log('WebSocket message', { url: url, size: e.data ? e.data.length : 0 });
                });
                
                ws.addEventListener('close', function() {
                    self.activeWebSockets = Math.max(0, self.activeWebSockets - 1);
                    var idx = self.webSocketDetails.findIndex(function(d) { return d.url === url; });
                    if (idx > -1) self.webSocketDetails.splice(idx, 1);
                    self._log('WebSocket closed', { url: url });
                });
                
                ws.addEventListener('error', function() {
                    self.activeWebSockets = Math.max(0, self.activeWebSockets - 1);
                    var idx = self.webSocketDetails.findIndex(function(d) { return d.url === url; });
                    if (idx > -1) self.webSocketDetails.splice(idx, 1);
                    self._log('WebSocket error', { url: url });
                });
                
                return ws;
            };
            
            // Preserve prototype chain
            window.WebSocket.prototype = this._originalWebSocket.prototype;
            window.WebSocket.CONNECTING = this._originalWebSocket.CONNECTING;
            window.WebSocket.OPEN = this._originalWebSocket.OPEN;
            window.WebSocket.CLOSING = this._originalWebSocket.CLOSING;
            window.WebSocket.CLOSED = this._originalWebSocket.CLOSED;
        },
        
        // ===== SSE TRACKING =====
        
        _setupSSETracking: function() {
            var self = this;
            this._originalEventSource = window.EventSource;
            
            if (!this._originalEventSource) {
                self._log('EventSource not supported in this browser');
                return;
            }
            
            window.EventSource = function(url, config) {
                var es = config
                    ? new self._originalEventSource(url, config)
                    : new self._originalEventSource(url);
                
                self.activeSSEConnections++;
                self.sseDetails.push({
                    url: url,
                    openTime: Date.now(),
                    state: 'connecting'
                });
                self._log('SSE connecting', { url: url });
                
                es.addEventListener('open', function() {
                    self.lastSSEActivity = Date.now();
                    var detail = self.sseDetails.find(function(d) { return d.url === url; });
                    if (detail) detail.state = 'open';
                    self._log('SSE opened', { url: url });
                });
                
                es.addEventListener('message', function(e) {
                    self.lastSSEActivity = Date.now();
                    self._log('SSE message', { url: url });
                });
                
                es.addEventListener('error', function() {
                    self.activeSSEConnections = Math.max(0, self.activeSSEConnections - 1);
                    var idx = self.sseDetails.findIndex(function(d) { return d.url === url; });
                    if (idx > -1) self.sseDetails.splice(idx, 1);
                    self._log('SSE error/closed', { url: url });
                });
                
                return es;
            };
            
            window.EventSource.prototype = this._originalEventSource.prototype;
            window.EventSource.CONNECTING = this._originalEventSource.CONNECTING;
            window.EventSource.OPEN = this._originalEventSource.OPEN;
            window.EventSource.CLOSED = this._originalEventSource.CLOSED;
        },
        
        // ===== IFRAME TRACKING =====
        
        _setupIframeTracking: function() {
            var self = this;
            
            // Observe for new iframes being added
            var observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(m) {
                    m.addedNodes.forEach(function(node) {
                        if (node.tagName === 'IFRAME') {
                            self._injectIntoIframe(node);
                        }
                    });
                });
            });
            
            observer.observe(document.body || document.documentElement, {
                childList: true,
                subtree: true
            });
            
            this._observers.push(observer);
            
            // Inject into existing iframes
            document.querySelectorAll('iframe').forEach(function(iframe) {
                self._injectIntoIframe(iframe);
            });
            
            this._log('iframe tracking initialized');
        },
        
        _injectIntoIframe: function(iframe) {
            var self = this;
            
            try {
                var iframeDoc = iframe.contentDocument || (iframe.contentWindow && iframe.contentWindow.document);
                
                if (!iframeDoc) {
                    self._log('Cannot access iframe (no document)', { src: iframe.src });
                    return;
                }
                
                // Check if already instrumented
                if (iframe.contentWindow.__waitless__) {
                    self._log('iframe already instrumented', { src: iframe.src });
                    return;
                }
                
                // Note: Full injection would require eval'ing the entire script
                // For now, we track iframe load/ready state
                self.iframeStatus.push({
                    src: iframe.src || 'inline',
                    loaded: iframeDoc.readyState === 'complete',
                    accessible: true
                });
                
                iframe.addEventListener('load', function() {
                    self._log('iframe loaded', { src: iframe.src });
                    var status = self.iframeStatus.find(function(s) { return s.src === (iframe.src || 'inline'); });
                    if (status) status.loaded = true;
                });
                
                self._log('iframe registered', { src: iframe.src });
            } catch (e) {
                // Cross-origin iframe - cannot access
                self.iframeStatus.push({
                    src: iframe.src || 'inline',
                    loaded: false,
                    accessible: false,
                    error: 'cross-origin'
                });
                self._log('Cannot access iframe (cross-origin)', { src: iframe.src });
            }
        },
        
        // ===== PUBLIC API =====
        
        getStatus: function() {
            return {
                stable: this.isStable(),
                pending_requests: this.pendingRequests,
                last_mutation_time: this.lastMutationTime,
                mutation_rate: this.getMutationRate(),  // mutations per second
                active_animations: this.activeAnimations + this.activeTransitions,
                layout_shifting: this.layoutShifting,
                pending_request_details: this.pendingRequestDetails.slice(),
                // WebSocket/SSE status
                active_websockets: this.activeWebSockets,
                active_sse: this.activeSSEConnections,
                last_websocket_activity: this.lastWebSocketActivity,
                last_sse_activity: this.lastSSEActivity,
                websocket_details: this.webSocketDetails.slice(),
                sse_details: this.sseDetails.slice(),
                timeline: this.timeline.slice(-20)
            };
        },
        
        isStable: function() {
            if (this.pendingRequests > 0) return false;
            
            var timeSinceLastMutation = Date.now() - this.lastMutationTime;
            if (timeSinceLastMutation < 100) return false;
            
            return true;
        },
        
        isAlive: function() {
            return this._initialized === true;
        },
        
        // Cleanup (for testing)
        destroy: function() {
            this._observers.forEach(function(obs) {
                obs.disconnect();
            });
            
            if (this._originalFetch) {
                window.fetch = this._originalFetch;
            }
            if (this._originalXHROpen) {
                XMLHttpRequest.prototype.open = this._originalXHROpen;
            }
            if (this._originalXHRSend) {
                XMLHttpRequest.prototype.send = this._originalXHRSend;
            }
            if (this._layoutCheckInterval) {
                clearInterval(this._layoutCheckInterval);
            }
            if (this._originalWebSocket) {
                window.WebSocket = this._originalWebSocket;
            }
            if (this._originalEventSource) {
                window.EventSource = this._originalEventSource;
            }
            
            this._initialized = false;
            this._log('Waitless instrumentation destroyed');
        }
    };
    
    return window.__waitless__.init();
})();
"""

# Script to check if instrumentation is alive
CHECK_ALIVE_SCRIPT = """
return window.__waitless__ && window.__waitless__.isAlive && window.__waitless__.isAlive();
"""

# Script to get current stability status
GET_STATUS_SCRIPT = """
if (window.__waitless__ && window.__waitless__.getStatus) {
    return window.__waitless__.getStatus();
}
return null;
"""

# Script to get full timeline for diagnostics
GET_TIMELINE_SCRIPT = """
if (window.__waitless__) {
    return {
        timeline: window.__waitless__.timeline,
        pending_request_details: window.__waitless__.pendingRequestDetails
    };
}
return null;
"""

# Script to update configuration
UPDATE_CONFIG_SCRIPT = """
if (window.__waitless__) {
    window.__waitless__.config = Object.assign(window.__waitless__.config, arguments[0]);
    return true;
}
return false;
"""
