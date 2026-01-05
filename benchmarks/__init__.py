"""
Waitless Benchmarks

This module contains performance benchmarks for measuring
the overhead of Waitless instrumentation and stabilization.
"""

from .overhead_test import (
    measure_injection_time,
    measure_poll_overhead,
    measure_stabilization_time,
    run_all_benchmarks,
)

__all__ = [
    'measure_injection_time',
    'measure_poll_overhead',
    'measure_stabilization_time',
    'run_all_benchmarks',
]
