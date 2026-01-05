"""
Unit tests for framework adapters (React, Angular, Vue).
"""

import pytest
from waitless.adapters import (
    FrameworkAdapter,
    get_adapter,
    get_available_adapters,
    ReactAdapter,
    AngularAdapter,
    VueAdapter,
)


class TestAdapterRegistry:
    """Tests for adapter registration and retrieval."""
    
    def test_get_available_adapters(self):
        """Test that available adapters are listed."""
        adapters = get_available_adapters()
        assert 'react' in adapters
        assert 'angular' in adapters
        assert 'vue' in adapters
    
    def test_get_adapter_react(self):
        """Test getting React adapter by name."""
        adapter = get_adapter('react')
        assert adapter is not None
        assert isinstance(adapter, ReactAdapter)
        assert adapter.name == 'react'
    
    def test_get_adapter_angular(self):
        """Test getting Angular adapter by name."""
        adapter = get_adapter('angular')
        assert adapter is not None
        assert isinstance(adapter, AngularAdapter)
        assert adapter.name == 'angular'
    
    def test_get_adapter_vue(self):
        """Test getting Vue adapter by name."""
        adapter = get_adapter('vue')
        assert adapter is not None
        assert isinstance(adapter, VueAdapter)
        assert adapter.name == 'vue'
    
    def test_get_adapter_case_insensitive(self):
        """Test that adapter names are case-insensitive."""
        assert get_adapter('REACT') is not None
        assert get_adapter('React') is not None
        assert get_adapter('react') is not None
    
    def test_get_adapter_unknown(self):
        """Test that unknown adapter returns None."""
        adapter = get_adapter('unknown')
        assert adapter is None


class TestReactAdapter:
    """Tests for React framework adapter."""
    
    @pytest.fixture
    def adapter(self):
        return ReactAdapter()
    
    def test_adapter_name(self, adapter):
        """Test adapter name property."""
        assert adapter.name == 'react'
    
    def test_detection_script_present(self, adapter):
        """Test detection script is defined."""
        script = adapter.detection_script
        assert script is not None
        assert len(script) > 0
    
    def test_detection_script_checks_devtools(self, adapter):
        """Test detection checks for React DevTools."""
        script = adapter.detection_script
        assert '__REACT_DEVTOOLS_GLOBAL_HOOK__' in script
    
    def test_detection_script_checks_fiber(self, adapter):
        """Test detection checks for React Fiber."""
        script = adapter.detection_script
        assert '__reactFiber' in script or '__reactContainer' in script
    
    def test_instrumentation_script_present(self, adapter):
        """Test instrumentation script is defined."""
        script = adapter.instrumentation_script
        assert script is not None
        assert len(script) > 0
    
    def test_instrumentation_hooks_commit(self, adapter):
        """Test instrumentation hooks into React commits."""
        script = adapter.instrumentation_script
        assert 'onCommitFiberRoot' in script
    
    def test_status_script_present(self, adapter):
        """Test status script is defined."""
        script = adapter.get_status_script()
        assert script is not None
        assert len(script) > 0
    
    def test_status_script_returns_object(self, adapter):
        """Test status script returns proper structure."""
        script = adapter.get_status_script()
        assert 'stable' in script
        assert 'details' in script


class TestAngularAdapter:
    """Tests for Angular framework adapter."""
    
    @pytest.fixture
    def adapter(self):
        return AngularAdapter()
    
    def test_adapter_name(self, adapter):
        """Test adapter name property."""
        assert adapter.name == 'angular'
    
    def test_detection_script_present(self, adapter):
        """Test detection script is defined."""
        script = adapter.detection_script
        assert script is not None
        assert len(script) > 0
    
    def test_detection_script_checks_ng_version(self, adapter):
        """Test detection checks for ng-version attribute."""
        script = adapter.detection_script
        assert 'ng-version' in script
    
    def test_instrumentation_script_present(self, adapter):
        """Test instrumentation script is defined."""
        script = adapter.instrumentation_script
        assert script is not None
        assert len(script) > 0
    
    def test_instrumentation_uses_testability(self, adapter):
        """Test instrumentation uses Angular testability API."""
        script = adapter.instrumentation_script
        assert 'getAllAngularTestabilities' in script or 'Zone' in script
    
    def test_status_script_present(self, adapter):
        """Test status script is defined."""
        script = adapter.get_status_script()
        assert script is not None
        assert 'stable' in script


class TestVueAdapter:
    """Tests for Vue framework adapter."""
    
    @pytest.fixture
    def adapter(self):
        return VueAdapter()
    
    def test_adapter_name(self, adapter):
        """Test adapter name property."""
        assert adapter.name == 'vue'
    
    def test_detection_script_present(self, adapter):
        """Test detection script is defined."""
        script = adapter.detection_script
        assert script is not None
        assert len(script) > 0
    
    def test_detection_script_checks_vue_devtools(self, adapter):
        """Test detection checks for Vue DevTools."""
        script = adapter.detection_script
        assert '__VUE_DEVTOOLS_GLOBAL_HOOK__' in script or '__VUE__' in script
    
    def test_instrumentation_script_present(self, adapter):
        """Test instrumentation script is defined."""
        script = adapter.instrumentation_script
        assert script is not None
        assert len(script) > 0
    
    def test_status_script_present(self, adapter):
        """Test status script is defined."""
        script = adapter.get_status_script()
        assert script is not None
        assert 'stable' in script


class TestAdapterInterface:
    """Tests for abstract adapter interface."""
    
    def test_all_adapters_have_required_methods(self):
        """Test that all adapters implement required interface."""
        for name in get_available_adapters():
            adapter = get_adapter(name)
            assert hasattr(adapter, 'name')
            assert hasattr(adapter, 'detection_script')
            assert hasattr(adapter, 'instrumentation_script')
            assert hasattr(adapter, 'get_status_script')
            
            # Properties should return strings
            assert isinstance(adapter.name, str)
            assert isinstance(adapter.detection_script, str)
            assert isinstance(adapter.instrumentation_script, str)
            assert isinstance(adapter.get_status_script(), str)
