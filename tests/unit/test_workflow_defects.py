import pytest
from tools.workflow_benchmark import workflow_benchmark
pytestmark=[pytest.mark.unit,pytest.mark.regression]


def test_five_stateful_faults_are_detected_against_passing_references():
    result=workflow_benchmark()
    assert result['detected']==result['total']==5
    assert result['reference_failures']==0


def test_workflow_traceability_links_resolve_to_existing_test_functions():
    import ast,json
    from pathlib import Path
    from healthcare_quality.workflow import WORKFLOW_RULES
    root=Path(__file__).resolve().parents[1]
    mapping=json.loads((root/"data/workflow-traceability.json").read_text())
    names={node.name for file in root.rglob("test_*.py") for node in ast.walk(ast.parse(file.read_text())) if isinstance(node,ast.FunctionDef)}
    assert set(mapping)=={r["id"] for r in WORKFLOW_RULES}
    assert all(values and set(values)<=names for values in mapping.values())
