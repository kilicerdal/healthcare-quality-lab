import pytest
from tools.benchmark import benchmark

pytestmark = [pytest.mark.unit,pytest.mark.regression]


def test_all_authored_defect_seeds_are_detected_against_passing_reference():
    result=benchmark()
    assert result["reference_cases"]==28
    assert result["reference_failures"]==[]
    assert result["detected"]==result["total"]==7
