"""
Vue framework adapter for detecting Vue-specific settling work.

Detects Vue by looking for __vue__ property or Vue DevTools hook.
Monitors Vue's nextTick queue to detect when Vue has finished updating.
"""

from .base import FrameworkAdapter


class VueAdapter(FrameworkAdapter):
    """
    Adapter for Vue framework (Vue 2 and Vue 3).
    
    Hooks into Vue's nextTick mechanism and watcher queue to detect
    when Vue has finished processing reactive updates.
    """
    
    @property
    def name(self) -> str:
        return 'vue'
    
    @property
    def detection_script(self) -> str:
        return """
        (function() {
            // Check for Vue DevTools hook
            if (window.__VUE_DEVTOOLS_GLOBAL_HOOK__) return true;
            
            // Check for Vue 3 app
            if (window.__VUE__) return true;
            
            // Check for Vue 2 instances on elements
            var elements = document.querySelectorAll('[data-v-app], [id="app"]');
            for (var i = 0; i < elements.length; i++) {
                if (elements[i].__vue__ || elements[i].__vue_app__) {
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
            if (window.__waitless__._vueHooked) return true;
            
            window.__waitless__.framework = window.__waitless__.framework || {};
            window.__waitless__.framework.vue = {
                lastUpdateTime: 0,
                pendingTicks: 0,
                isSettled: true
            };
            
            var hook = window.__VUE_DEVTOOLS_GLOBAL_HOOK__;
            var originals = window.__waitless__._vueOriginals = {};
            if (hook) {
                // Vue 3 DevTools hook. Reuse a stable handler if the hook has no off().
                if (hook.on) {
                    var updateHandler = hook.__waitlessVueUpdateHandler;
                    if (!updateHandler) {
                        updateHandler = function() {
                            var vue = window.__waitless__ && window.__waitless__.framework && window.__waitless__.framework.vue;
                            if (!vue) return;
                            vue.lastUpdateTime = Date.now();
                            vue.isSettled = false;
                            window.__waitless__._log('Vue component updated');

                            setTimeout(function() {
                                var current = window.__waitless__ && window.__waitless__.framework && window.__waitless__.framework.vue;
                                if (current) current.isSettled = true;
                            }, 50);
                        };
                        hook.__waitlessVueUpdateHandler = updateHandler;
                        hook.on('component:updated', updateHandler);
                    }
                    originals.hook = hook;
                    originals.updateHandler = updateHandler;
                }

                // Vue 2 compatibility
                if (hook.Vue && hook.Vue.nextTick) {
                    var originalNextTick = hook.Vue.nextTick;
                    originals.vue = hook.Vue;
                    originals.nextTick = originalNextTick;
                    hook.Vue.nextTick = function(callback, context) {
                        var vue = window.__waitless__ && window.__waitless__.framework && window.__waitless__.framework.vue;
                        if (vue) {
                            vue.pendingTicks++;
                            vue.isSettled = false;
                        }

                        var wrappedCallback = function() {
                            var current = window.__waitless__ && window.__waitless__.framework && window.__waitless__.framework.vue;
                            if (current) {
                                current.pendingTicks--;
                                current.lastUpdateTime = Date.now();
                                if (current.pendingTicks === 0) current.isSettled = true;
                            }
                            if (callback) return callback.apply(this, arguments);
                        };

                        return originalNextTick.call(this, wrappedCallback, context);
                    };
                }
            }
            
            window.__waitless__._vueHooked = true;
            window.__waitless__._log('Vue adapter installed');
            return true;
        })();
        """
    
    @property
    def uninstall_script(self) -> str:
        return """
        (function() {
            if (!window.__waitless__) return true;
            var originals = window.__waitless__._vueOriginals || {};
            if (originals.vue && originals.nextTick) {
                originals.vue.nextTick = originals.nextTick;
            }
            if (originals.hook && originals.updateHandler && originals.hook.off) {
                originals.hook.off('component:updated', originals.updateHandler);
                delete originals.hook.__waitlessVueUpdateHandler;
            }
            if (window.__waitless__.framework) delete window.__waitless__.framework.vue;
            delete window.__waitless__._vueOriginals;
            delete window.__waitless__._vueHooked;
            return true;
        })();
        """

    def get_status_script(self) -> str:
        return """
        (function() {
            if (!window.__waitless__ || !window.__waitless__.framework || !window.__waitless__.framework.vue) {
                return { stable: true, details: 'Vue not detected' };
            }
            
            var vue = window.__waitless__.framework.vue;
            var timeSinceUpdate = Date.now() - vue.lastUpdateTime;
            var isStable = vue.isSettled && timeSinceUpdate > 100;
            
            return {
                stable: isStable,
                details: isStable 
                    ? 'Vue idle, last update ' + timeSinceUpdate + 'ms ago'
                    : 'Vue updating, pending ticks=' + vue.pendingTicks
            };
        })();
        """
