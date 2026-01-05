"""
Base adapter interface for framework-specific hooks.

Adapters detect when a framework has finished its internal work
(rendering, effects, zone tasks) beyond what DOM observation captures.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class FrameworkAdapter(ABC):
    """
    Base class for framework-specific stability detection.
    
    Subclasses implement framework-specific JavaScript that detects
    when the framework has finished its internal processing.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this adapter (e.g., 'react', 'angular')."""
        pass
    
    @property
    @abstractmethod
    def detection_script(self) -> str:
        """
        JavaScript that detects if this framework is present on the page.
        Should return true if the framework is detected.
        """
        pass
    
    @property
    @abstractmethod
    def instrumentation_script(self) -> str:
        """
        JavaScript to inject for monitoring framework activity.
        Should set window.__waitless__.framework[name] with status info.
        """
        pass
    
    @abstractmethod
    def get_status_script(self) -> str:
        """
        JavaScript that returns the current framework stability status.
        Should return { stable: bool, details: string }.
        """
        pass


def get_adapter(name: str) -> Optional['FrameworkAdapter']:
    """Get a framework adapter by name."""
    # Lazy imports to avoid circular dependency
    from .react import ReactAdapter
    from .angular import AngularAdapter
    from .vue import VueAdapter
    
    adapters = {
        'react': ReactAdapter,
        'angular': AngularAdapter,
        'vue': VueAdapter,
    }
    adapter_class = adapters.get(name.lower())
    if adapter_class:
        return adapter_class()
    return None


def get_available_adapters() -> list:
    """List available adapter names."""
    return ['react', 'angular', 'vue']
