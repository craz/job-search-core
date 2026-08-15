"""Unit tests for isolated Core application metadata."""

from job_search_core.app import COMPONENT_NAME, component_info


def test_component_info_is_stable_and_machine_readable() -> None:
    """Component metadata must identify Core and report a healthy process."""
    result = component_info()

    assert result.component == COMPONENT_NAME
    assert result.status == "ok"
    assert result.version
