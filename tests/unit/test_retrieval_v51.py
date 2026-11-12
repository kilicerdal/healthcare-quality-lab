import pytest
from healthcare_quality.evaluation import retrieve
pytestmark=[pytest.mark.unit,pytest.mark.regression,pytest.mark.ai]

@pytest.mark.parametrize('query',['hc','wf','007','999','hc 007','WF-999','prefixHC-007suffix'])
def test_namespace_and_number_fragments_are_not_sources(query):assert retrieve(query)==[]

def test_explicit_sources_take_precedence_over_unrelated_words_and_preserve_order():
    result=retrieve('WF-004 HC-007 WF-004 hospital eligibility')
    assert [r['rule_id'] for r in result]==['WF-004','HC-007']
    assert all(r['match_method']=='exact_rule_id' for r in result)


def test_keyword_results_have_actual_word_matches_without_namespace_fragments():
    result=retrieve('payment ledger')
    assert result and result[0]['rule_id']=='WF-004'
    assert all(set(r['matched_terms'])&{'payment','ledger'} for r in result)
    assert all(r['match_method']=='lexical_overlap' for r in result)

@pytest.mark.parametrize('limit',[0,-1,True,14,'3'])
def test_invalid_limits_are_rejected(limit):
    with pytest.raises(ValueError):retrieve('payment',limit)
