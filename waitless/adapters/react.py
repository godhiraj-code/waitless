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
            
            var originals = window.__waitless__._reactOriginals = {};
            var hook = window.__REACT_DEVTOOLS_GLOBAL_HOOK__;
            if (hook && hook.onCommitFiberRoot) {
                var originalOnCommit = hook.onCommitFiberRoot;
                originals.hook = hook;
                originals.onCommitFiberRoot = originalOnCommit;
                hook.onCommitFiberRoot = function(id, root, priority) {
                    var react = window.__waitless__ && window.__waitless__.framework && window.__waitless__.framework.react;
                    if (react) {
                        react.lastCommitTime = Date.now();
                        react.isSettled = false;
                        window.__waitless__._log('React commit', { priority: priority });

                        setTimeout(function() {
                            var current = window.__waitless__ && window.__waitless__.framework && window.__waitless__.framework.react;
                            if (current) current.isSettled = true;
                        }, 50);
                    }

                    return originalOnCommit.apply(this, arguments);
                };
            }
            
            // Also try to intercept React's scheduler if available
            if (window.scheduler && window.scheduler.unstable_scheduleCallback) {
                var originalSchedule = window.scheduler.unstable_scheduleCallback;
                originals.scheduler = window.scheduler;
                originals.scheduleCallback = originalSchedule;
                window.scheduler.unstable_scheduleCallback = function(priority, callback) {
                    var react = window.__waitless__ && window.__waitless__.framework && window.__waitless__.framework.react;
                    if (react) react.pendingUpdates++;
                    var wrappedCallback = function() {
                        var result = callback.apply(this, arguments);
                        var current = window.__waitless__ && window.__waitless__.framework && window.__waitless__.framework.react;
                        if (current) current.pendingUpdates--;
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
    
    @property
    def uninstall_script(self) -> str:
        return """
        (function() {
            if (!window.__waitless__) return true;
            var originals = window.__waitless__._reactOriginals || {};
            if (originals.hook && originals.onCommitFiberRoot) {
                originals.hook.onCommitFiberRoot = originals.onCommitFiberRoot;
            }
            if (originals.scheduler && originals.scheduleCallback) {
                originals.scheduler.unstable_scheduleCallback = originals.scheduleCallback;
            }
            if (window.__waitless__.framework) delete window.__waitless__.framework.react;
            delete window.__waitless__._reactOriginals;
            delete window.__waitless__._reactHooked;
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
