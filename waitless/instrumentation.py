"""
JavaScript instrumentation for browser-side stability monitoring.
"""

INSTRUMENTATION_SCRIPT = """
(function(suppliedConfig) {
    suppliedConfig = suppliedConfig || {};
    // Avoid re-initialization
    if (window.__waitless__ && window.__waitless__._initialized) {
        return window.__waitless__;
    }
    
    window.__waitless__ = {
        _initialized: true,
        _version: '1.0.4',
        
        // State tracking
        pendingRequests: 0,
        lastMutationTime: Date.now(),
        activeAnimations: 0,
        activeTransitions: 0,
        layoutShifting: false,
        layoutReady: false,
        
        // WebSocket/SSE tracking
        activeWebSockets: 0,
        activeSSEConnections: 0,
        lastWebSocketActivity: 0,
        lastSSEActivity: 0,
        webSocketDetails: [],
        _nextWebSocketId: 1,
        sseDetails: [],
        _nextSSEId: 1,
        
        // iframe tracking
        iframeStatus: [],  // Status from child iframes
        _iframeRecords: new WeakMap(),
        _nextIframeId: 1,
        
        // Timeline for diagnostics (circular buffer)
        timeline: [],
        _maxTimelineEntries: 100,
        
        // Request tracking for diagnostics
        pendingRequestDetails: [],
        
        // Configuration (updated from Python)
        config: Object.assign({
            trackLayout: true,
            trackAnimations: true,
            trackWebSocket: false,
            trackSSE: false,
            webSocketQuietTime: 500,  // ms of silence for stability
            domSettleTime: 100,  // ms the DOM must remain quiet
            trackIframes: false,
            redactQueryStrings: true
        }, suppliedConfig),
        
        // Lifecycle
        _observers: [],
        _cleanupCallbacks: [],
        _originalFetch: null,
        _originalXHROpen: null,
        _originalXHRSend: null,
        _originalWebSocket: null,
        _originalEventSource: null,
        
        // ===== INITIALIZATION =====
        
        init: function() {
            this._setupMutationObserver();
            this._setupNetworkInterceptors();
            if (this.config.trackAnimations) {
                this._setupAnimationTracking();
            }
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

        _registerCleanup: function(callback) {
            var self = this;
            var active = true;
            var cleanup = function() {
                if (!active) return;
                active = false;
                var idx = self._cleanupCallbacks.indexOf(cleanup);
                if (idx > -1) self._cleanupCallbacks.splice(idx, 1);
                callback();
            };
            this._cleanupCallbacks.push(cleanup);
            return cleanup;
        },

        _listen: function(target, type, handler, options) {
            target.addEventListener(type, handler, options);
            return this._registerCleanup(function() {
                target.removeEventListener(type, handler, options);
            });
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
        _maxMutationTimestamps: 10000,
        _observedShadowRoots: new WeakSet(),
        _trackedShadowRoots: [],

        _pruneMutationTimestamps: function(now) {
            var cutoff = now - this._mutationWindowMs;
            var firstRecent = 0;
            while (firstRecent < this._mutationTimestamps.length &&
                   this._mutationTimestamps[firstRecent] <= cutoff) {
                firstRecent++;
            }
            if (firstRecent > 0) {
                this._mutationTimestamps.splice(0, firstRecent);
            }
            if (this._mutationTimestamps.length > this._maxMutationTimestamps) {
                this._mutationTimestamps.splice(
                    0,
                    this._mutationTimestamps.length - this._maxMutationTimestamps
                );
            }
        },

        _recordMutations: function(mutations, label) {
            var now = Date.now();
            this.lastMutationTime = now;
            // MutationObserver callbacks can contain many MutationRecords. Count
            // each record, not merely each callback invocation.
            for (var i = 0; i < mutations.length; i++) {
                this._mutationTimestamps.push(now);
            }
            this._pruneMutationTimestamps(now);
            this._log(label, { count: mutations.length, rate: this.getMutationRate() });
        },
        
        _setupMutationObserver: function() {
            var self = this;
            var observer = new MutationObserver(function(mutations) {
                self._recordMutations(mutations, 'DOM mutation');
                
                // Check for new shadow roots in added nodes
                mutations.forEach(function(mutation) {
                    mutation.addedNodes.forEach(function(node) {
                        if (node.nodeType === 1) { // Element node
                            self._observeShadowRoots(node);
                        }
                    });
                });
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
                    if (self.config.trackLayout) {
                        self._trackedShadowRoots.push(node.shadowRoot);
                    }
                    
                    var observer = new MutationObserver(function(mutations) {
                        self._recordMutations(mutations, 'Shadow DOM mutation');
                        
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
            this._pruneMutationTimestamps(now);
            return this._mutationTimestamps.length;
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

                try {
                    return self._originalXHRSend.apply(this, arguments);
                } catch (error) {
                    // Synchronous failures (for example, send() before open()) do
                    // not emit loadend. Balance the counter before preserving the
                    // browser's original exception behavior.
                    self._requestEnded(url, 'xhr', 'error');
                    throw error;
                }
            };
        },

        _redactUrl: function(url) {
            var value = String(url || 'unknown');
            if (!this.config.redactQueryStrings) return value;

            try {
                var parsed = new URL(value, window.location.href);
                parsed.username = '';
                parsed.password = '';
                parsed.search = '';
                parsed.hash = '';

                if (value.indexOf('//') === 0) {
                    return '//' + parsed.host + parsed.pathname;
                }
                if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(value)) {
                    return parsed.toString();
                }
            } catch (error) {
                // Keep the safe string fallback for malformed or relative URLs.
            }
            return value.split(/[?#]/, 1)[0];
        },
        
        _requestStarted: function(url, type) {
            url = this._redactUrl(url);
            this.pendingRequests++;
            this.pendingRequestDetails.push({
                url: url,
                type: type,
                startTime: Date.now()
            });
            this._log('Request started', { url: url, type: type, pending: this.pendingRequests });
        },
        
        _requestEnded: function(url, type, status) {
            url = this._redactUrl(url);
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
            this._listen(document, 'animationstart', function(e) {
                self.activeAnimations++;
                self._log('Animation started', { name: e.animationName });
            }, true);
            
            this._listen(document, 'animationend', function(e) {
                self.activeAnimations = Math.max(0, self.activeAnimations - 1);
                self._log('Animation ended', { name: e.animationName });
            }, true);
            
            this._listen(document, 'animationcancel', function(e) {
                self.activeAnimations = Math.max(0, self.activeAnimations - 1);
                self._log('Animation cancelled', { name: e.animationName });
            }, true);
            
            // CSS Transitions
            this._listen(document, 'transitionstart', function(e) {
                self.activeTransitions++;
                self._log('Transition started', { property: e.propertyName });
            }, true);
            
            this._listen(document, 'transitionend', function(e) {
                self.activeTransitions = Math.max(0, self.activeTransitions - 1);
                self._log('Transition ended', { property: e.propertyName });
            }, true);
            
            this._listen(document, 'transitioncancel', function(e) {
                self.activeTransitions = Math.max(0, self.activeTransitions - 1);
                self._log('Transition cancelled', { property: e.propertyName });
            }, true);
        },
        
        // ===== LAYOUT TRACKING =====
        
        _setupLayoutTracking: function() {
            var self = this;
            // Element keys must not keep detached DOM subtrees alive.
            this._lastPositions = new WeakMap();
            this._layoutSampleCount = 0;
            this.layoutReady = false;
            this._layoutCheckInterval = null;

            // Establish positions synchronously, then require a later sample
            // before strict mode can treat layout as stable.
            this._checkLayoutStability();

            // Layout reads force style/layout calculation. A 250ms cadence is
            // responsive enough for stabilization without scanning at 20Hz.
            this._layoutCheckInterval = setInterval(function() {
                self._checkLayoutStability();
            }, 250);
        },
        
        _checkLayoutStability: function() {
            // Track only interactive elements. Shadow roots are discovered by
            // the mutation observer, so this path never needs querySelectorAll('*').
            var elements = [];
            var roots = [document];
            this._trackedShadowRoots = this._trackedShadowRoots.filter(function(root) {
                return root.host && root.host.isConnected;
            });
            roots = roots.concat(this._trackedShadowRoots);

            var collectElements = function(root) {
                var found = root.querySelectorAll('button, a, input, [onclick], [role="button"]');
                for (var i = 0; i < found.length; i++) {
                    elements.push(found[i]);
                }
            };

            roots.forEach(collectElements);
            
            var isShifting = false;
            var self = this;
            
            elements.forEach(function(el) {
                var rect = el.getBoundingClientRect();
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
            this._layoutSampleCount++;
            this.layoutReady = this._layoutSampleCount >= 2;
        },
        
        // ===== WEBSOCKET TRACKING =====
        
        _setupWebSocketTracking: function() {
            var self = this;
            this._originalWebSocket = window.WebSocket;
            
            window.WebSocket = function(url, protocols) {
                var ws = arguments.length > 1
                    ? new self._originalWebSocket(url, protocols)
                    : new self._originalWebSocket(url);
                
                var safeUrl = self._redactUrl(url);
                var detail = {
                    id: 'ws-' + self._nextWebSocketId++,
                    url: safeUrl,
                    openTime: Date.now(),
                    state: 'connecting'
                };
                var finalized = false;
                var socketCleanups = [];
                self.activeWebSockets++;
                self.webSocketDetails.push(detail);
                self._log('WebSocket connecting', { url: safeUrl });

                var finalize = function(eventName) {
                    if (finalized) return;
                    finalized = true;
                    socketCleanups.slice().forEach(function(cleanup) { cleanup(); });
                    self.activeWebSockets = Math.max(0, self.activeWebSockets - 1);
                    var idx = self.webSocketDetails.indexOf(detail);
                    if (idx > -1) self.webSocketDetails.splice(idx, 1);
                    self._log(eventName, { url: safeUrl });
                };
                
                socketCleanups.push(self._listen(ws, 'open', function() {
                    self.lastWebSocketActivity = Date.now();
                    detail.state = 'open';
                    self._log('WebSocket opened', { url: safeUrl });
                }));
                
                socketCleanups.push(self._listen(ws, 'message', function(e) {
                    self.lastWebSocketActivity = Date.now();
                    self._log('WebSocket message', { url: safeUrl, size: e.data ? e.data.length : 0 });
                }));
                
                socketCleanups.push(self._listen(ws, 'close', function() {
                    finalize('WebSocket closed');
                }));
                
                socketCleanups.push(self._listen(ws, 'error', function() {
                    finalize('WebSocket error');
                }));
                
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
                var es = arguments.length > 1
                    ? new self._originalEventSource(url, config)
                    : new self._originalEventSource(url);

                var safeUrl = self._redactUrl(url);
                var detail = {
                    id: 'sse-' + self._nextSSEId++,
                    url: safeUrl,
                    openTime: Date.now(),
                    state: 'connecting'
                };
                var finalized = false;
                var sseCleanups = [];
                self.activeSSEConnections++;
                self.sseDetails.push(detail);
                self._log('SSE connecting', { url: safeUrl });

                var finalize = function(eventName) {
                    if (finalized) return;
                    finalized = true;
                    sseCleanups.slice().forEach(function(cleanup) { cleanup(); });
                    self.activeSSEConnections = Math.max(0, self.activeSSEConnections - 1);
                    var idx = self.sseDetails.indexOf(detail);
                    if (idx > -1) self.sseDetails.splice(idx, 1);
                    self._log(eventName, { url: safeUrl });
                };

                var originalClose = es.close.bind(es);
                es.close = function() {
                    try {
                        return originalClose();
                    } finally {
                        finalize('SSE closed');
                    }
                };
                sseCleanups.push(self._registerCleanup(function() {
                    es.close = originalClose;
                }));
                
                sseCleanups.push(self._listen(es, 'open', function() {
                    self.lastSSEActivity = Date.now();
                    detail.state = 'open';
                    self._log('SSE opened', { url: safeUrl });
                }));
                
                sseCleanups.push(self._listen(es, 'message', function(e) {
                    self.lastSSEActivity = Date.now();
                    self._log('SSE message', { url: safeUrl });
                }));
                
                sseCleanups.push(self._listen(es, 'error', function() {
                    // EventSource reports transient errors while reconnecting.
                    // Only CLOSED is terminal; otherwise keep the connection active.
                    if (es.readyState === self._originalEventSource.CLOSED) {
                        finalize('SSE error/closed');
                    } else {
                        detail.state = 'reconnecting';
                        self._log('SSE reconnecting', { url: safeUrl });
                    }
                }));
                
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
                        if (node.querySelectorAll) {
                            node.querySelectorAll('iframe').forEach(function(iframe) {
                                self._injectIntoIframe(iframe);
                            });
                        }
                    });
                    m.removedNodes.forEach(function(node) {
                        if (node.tagName === 'IFRAME') {
                            self._removeIframe(node);
                        }
                        if (node.querySelectorAll) {
                            node.querySelectorAll('iframe').forEach(function(iframe) {
                                self._removeIframe(iframe);
                            });
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
            var record = this._iframeRecords.get(iframe);
            if (record) {
                this._refreshIframeStatus(iframe, record);
                return;
            }

            record = {
                id: 'iframe-' + this._nextIframeId++,
                src: iframe.src || 'inline',
                loaded: false,
                accessible: false
            };
            this._iframeRecords.set(iframe, record);
            this.iframeStatus.push(record);

            record.loadCleanup = this._listen(iframe, 'load', function() {
                self._refreshIframeStatus(iframe, record);
                self._log('iframe loaded', { src: record.src });
            });
            this._refreshIframeStatus(iframe, record);
            this._log('iframe registered', { src: record.src });
        },

        _refreshIframeStatus: function(iframe, record) {
            try {
                var iframeDoc = iframe.contentDocument || (iframe.contentWindow && iframe.contentWindow.document);
                record.src = iframe.src || 'inline';
                if (!iframeDoc) {
                    record.loaded = false;
                    record.accessible = false;
                    record.error = 'no-document';
                    return;
                }
                record.loaded = iframeDoc.readyState === 'complete';
                record.accessible = true;
                delete record.error;
            } catch (e) {
                record.src = iframe.src || 'inline';
                record.loaded = false;
                record.accessible = false;
                record.error = 'cross-origin';
            }
        },

        _removeIframe: function(iframe) {
            var record = this._iframeRecords.get(iframe);
            if (!record) return;
            if (record.loadCleanup) record.loadCleanup();
            var idx = this.iframeStatus.indexOf(record);
            if (idx > -1) this.iframeStatus.splice(idx, 1);
            this._iframeRecords.delete(iframe);
            this._log('iframe removed', { src: record.src });
        },
        
        // ===== PUBLIC API =====
        
        getStatus: function() {
            var quietFor = Date.now() - this.lastMutationTime;
            return {
                stable: this.isStable(),
                pending_requests: this.pendingRequests,
                last_mutation_time: this.lastMutationTime,
                mutation_rate: this.getMutationRate(),  // mutations per second
                dom_quiet_for_ms: quietFor,
                dom_settle_time_ms: this.config.domSettleTime,
                active_animations: this.activeAnimations + this.activeTransitions,
                layout_shifting: this.layoutShifting,
                layout_ready: !this.config.trackLayout || this.layoutReady,
                pending_request_details: this.pendingRequestDetails.slice(),
                // WebSocket/SSE status
                active_websockets: this.activeWebSockets,
                active_sse: this.activeSSEConnections,
                last_websocket_activity: this.lastWebSocketActivity,
                last_sse_activity: this.lastSSEActivity,
                websocket_details: this.webSocketDetails.slice(),
                sse_details: this.sseDetails.slice(),
                iframe_status: this.iframeStatus.slice(),
                timeline: this.timeline.slice(-20)
            };
        },
        
        isStable: function() {
            if (this.pendingRequests > 0) return false;
            
            var timeSinceLastMutation = Date.now() - this.lastMutationTime;
            if (timeSinceLastMutation < this.config.domSettleTime) return false;
            
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
            this._cleanupCallbacks.slice().forEach(function(cleanup) {
                cleanup();
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
})(arguments[0]);
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
