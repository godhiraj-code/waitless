"""
Angular framework adapter for detecting Angular-specific settling work.

Detects Angular by looking for ng-version attribute or NgZone.
Monitors NgZone stability to detect when Angular has finished its work.
"""

from .base import FrameworkAdapter


class AngularAdapter(FrameworkAdapter):
    """
    Adapter for Angular framework.
    
    Hooks into Angular's NgZone to detect when all async tasks have completed
    and Angular is in a stable state.
    """
    
    @property
    def name(self) -> str:
        return 'angular'
    
    @property
    def detection_script(self) -> str:
        return """
        (function() {
            // Check for Angular version attribute
            if (document.querySelector('[ng-version]')) return true;
            
            // Check for Angular global (older versions)
            if (window.ng) return true;
            
            // Check for getAllAngularRootElements
            if (window.getAllAngularRootElements) return true;
            
            return false;
        })();
        """
    
    @property
    def instrumentation_script(self) -> str:
        return """
        (function() {
            if (!window.__waitless__) return false;
            if (window.__waitless__._angularHooked) return true;
            
            window.__waitless__.framework = window.__waitless__.framework || {};
            window.__waitless__.framework.angular = {
                isStable: true,
                lastStableTime: Date.now(),
                pendingTasks: 0
            };
            
            // Try to get NgZone from Angular's testability API
            var testability = window.getAllAngularTestabilities && window.getAllAngularTestabilities();
            if (testability && testability.length > 0) {
                testability.forEach(function(t) {
                    t.whenStable(function() {
                        window.__waitless__.framework.angular.isStable = true;
                        window.__waitless__.framework.angular.lastStableTime = Date.now();
                        window.__waitless__._log('Angular became stable');
                    });
                });
            }
            
            // Also try to hook into Zone.js if available
            if (window.Zone && window.Zone.current) {
                var originalRun = Zone.prototype.run;
                Zone.prototype.run = function(callback, applyThis, applyArgs) {
                    if (this.name === 'angular') {
                        window.__waitless__.framework.angular.isStable = false;
                        window.__waitless__.framework.angular.pendingTasks++;
                    }
                    var result = originalRun.apply(this, arguments);
                    if (this.name === 'angular') {
                        window.__waitless__.framework.angular.pendingTasks--;
                        if (window.__waitless__.framework.angular.pendingTasks === 0) {
                            window.__waitless__.framework.angular.isStable = true;
                            window.__waitless__.framework.angular.lastStableTime = Date.now();
                        }
                    }
                    return result;
                };
            }
            
            window.__waitless__._angularHooked = true;
            window.__waitless__._log('Angular adapter installed');
            return true;
        })();
        """
    
    def get_status_script(self) -> str:
        return """
        (function() {
            if (!window.__waitless__ || !window.__waitless__.framework || !window.__waitless__.framework.angular) {
                return { stable: true, details: 'Angular not detected' };
            }
            
            var angular = window.__waitless__.framework.angular;
            var timeSinceStable = Date.now() - angular.lastStableTime;
            
            return {
                stable: angular.isStable,
                details: angular.isStable 
                    ? 'NgZone stable, last activity ' + timeSinceStable + 'ms ago'
                    : 'NgZone unstable, pending=' + angular.pendingTasks
            };
        })();
        """
