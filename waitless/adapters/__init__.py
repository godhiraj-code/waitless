"""
Waitless Framework Adapters

This module provides optional framework-specific hooks for detecting
when React, Angular, or Vue have finished settling their internal work.
"""

from .base import FrameworkAdapter, get_adapter, get_available_adapters
from .react import ReactAdapter
from .angular import AngularAdapter
from .vue import VueAdapter

__all__ = [
    'FrameworkAdapter',
    'get_adapter',
    'get_available_adapters',
    'ReactAdapter',
    'AngularAdapter', 
    'VueAdapter',
]
