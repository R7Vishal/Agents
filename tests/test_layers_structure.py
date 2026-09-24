from pathlib import Path

from coding_agent.composition import build_default_runtime
from coding_agent.layers.mapping import current_layer_mappings


def test_layer_mapping_contains_12_components() -> None:
    mappings = current_layer_mappings()
    assert len(mappings) == 12
    assert any(item.layer_name.startswith("1. User Interface") for item in mappings)
    assert any(item.layer_name.startswith("12. Security & Governance") for item in mappings)


def test_composition_runtime_builds() -> None:
    runtime = build_default_runtime(Path("."))
    assert runtime.components.orchestrator
    assert runtime.components.ui
    assert len(runtime.layer_mappings) == 12
