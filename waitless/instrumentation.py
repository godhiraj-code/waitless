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
        _version: '0.1.0',
        
        // State tracking
        pendingRequests: 0,
        lastMutationTime: Date.now(),
        activeAnimations: 0,
        activeTransitions: 0,
        layoutShifting: false,
        
        // Timeline for diagnostics (circular buffer)
        timeline: [],
        _maxTimelineEntries: 100,
        
        // Request tracking for diagnostics
        pendingRequestDetails: [],
        
        // Configuration (updated from Python)
        config: {
            trackLayout: true,
            trackAnimations: true,
        },
        
        // Lifecycle
        _observers: [],
        _originalFetch: null,
        _originalXHROpen: null,
        _originalXHRSend: null,
        
        // ===== INITIALIZATION =====
        
        init: function() {
            this._setupMutationObserver();
            this._setupNetworkInterceptors();
            this._setupAnimationTracking();
            if (this.config.trackLayout) {
                this._setupLayoutTracking();
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
        
        _setupMutationObserver: function() {
            var self = this;
            var observer = new MutationObserver(function(mutations) {
                self.lastMutationTime = Date.now();
                self._log('DOM mutation', { count: mutations.length });
            });
            
            observer.observe(document.documentElement || document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                characterData: true
            });
            
            this._observers.push(observer);
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
            // Track key interactive elements
            var elements = document.querySelectorAll('button, a, input, [onclick], [role="button"]');
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
        
        // ===== PUBLIC API =====
        
        getStatus: function() {
            return {
                stable: this.isStable(),
                pending_requests: this.pendingRequests,
                last_mutation_time: this.lastMutationTime,
                active_animations: this.activeAnimations + this.activeTransitions,
                layout_shifting: this.layoutShifting,
                pending_request_details: this.pendingRequestDetails.slice(),
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
