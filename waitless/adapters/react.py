"""
React framework adapter for detecting React-specific settling work.

Detects React by looking for React DevTools hook or __REACT_DEVTOOLS_GLOBAL_HOOK__.
Monitors React commits and batch updates to detect when React has finished rendering.
"""

from .base import FrameworkAdapter


class ReactAdapter(FrameworkAdapter):
    """
    Adapter for React framework.
    
    Hooks into React's commit phase via the DevTools global hook to detect
    when React has finished reconciliation and committed changes to the DOM.
    """
    
    @property
    def name(self) -> str:
        return 'react'
    
    @property
    def detection_script(self) -> str:
        return """
        (function() {
            // Check for React DevTools hook (most reliable)
            if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) return true;
            
            // Check for React fiber root on body
            var root = document.getElementById('root') || document.body;
            for (var key in root) {
                if (key.startsWith('__reactFiber') || key.startsWith('__reactContainer')) {
                    return true;
                }
            }
            
            return false;
        })();
        """
    
    @property
    def instrumentation_script(self) -> str:
        return """
        (function() {
            if (!window.__waitless__) return false;
            if (window.__waitless__._reactHooked) return true;
            
            window.__waitless__.framework = window.__waitless__.framework || {};
            window.__waitless__.framework.react = {
                lastCommitTime: 0,
                pendingUpdates: 0,
                isSettled: true
            };
            
            var hook = window.__REACT_DEVTOOLS_GLOBAL_HOOK__;
            if (hook && hook.onCommitFiberRoot) {
                var originalOnCommit = hook.onCommitFiberRoot;
                hook.onCommitFiberRoot = function(id, root, priority) {
                    window.__waitless__.framework.react.lastCommitTime = Date.now();
                    window.__waitless__.framework.react.isSettled = false;
                    window.__waitless__._log('React commit', { priority: priority });
                    
                    // Mark as settled after a short delay (microtask completion)
                    setTimeout(function() {
                        window.__waitless__.framework.react.isSettled = true;
                    }, 50);
                    
                    return originalOnCommit.apply(this, arguments);
                };
            }
            
            // Also try to intercept React's scheduler if available
            if (window.scheduler && window.scheduler.unstable_scheduleCallback) {
                var originalSchedule = window.scheduler.unstable_scheduleCallback;
                window.scheduler.unstable_scheduleCallback = function(priority, callback) {
                    window.__waitless__.framework.react.pendingUpdates++;
                    var wrappedCallback = function() {
                        var result = callback.apply(this, arguments);
                        window.__waitless__.framework.react.pendingUpdates--;
                        return result;
                    };
                    return originalSchedule.call(this, priority, wrappedCallback);
                };
            }
            
            window.__waitless__._reactHooked = true;
            window.__waitless__._log('React adapter installed');
            return true;
        })();
        """
    
    def get_status_script(self) -> str:
        return """
        (function() {
            if (!window.__waitless__ || !window.__waitless__.framework || !window.__waitless__.framework.react) {
                return { stable: true, details: 'React not detected' };
            }
            
            var react = window.__waitless__.framework.react;
            var timeSinceCommit = Date.now() - react.lastCommitTime;
            var isStable = react.isSettled && timeSinceCommit > 100;
            
            return {
                stable: isStable,
                details: isStable 
                    ? 'React idle, last commit ' + timeSinceCommit + 'ms ago'
                    : 'React updating, pending=' + react.pendingUpdates
            };
        })();
        """
