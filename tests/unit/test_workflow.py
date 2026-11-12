import json
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading
import pytest
from healthcare_quality.workflow import ACTORS,MEMBERS,ClaimStore,WorkflowService,WorkflowError,WORKFLOW_HASH

BASE={"claim_id":"CLM-100","member_id":"M100","service":"medical","amount_cents":100000}
pytestmark=[pytest.mark.unit,pytest.mark.regression]


def submit(workflow,**changes):return workflow.submit("customer-m100",{**BASE,**changes})


@pytest.mark.smoke
def test_complete_lifecycle_records_expected_payment_and_events(workflow):
    first=submit(workflow)
    assert first["claim"]["status"]=="submitted"
    assert first["claim"]["revision"]==1
    assert first["claim"]["evaluation"]["decision"]=="approved"
    workflow.transition("adjuster-demo","CLM-100",{"target":"approved"})
    paid=workflow.transition("finance-demo","CLM-100",{"target":"paid"})
    assert paid["claim"]["status"]=="paid"
    assert paid["claim"]["revision"]==3
    assert paid["payment"]["amount_cents"]==90000
    assert [e["to_status"] for e in paid["events"]]==["submitted","approved","paid"]
    assert [e["actor_id"] for e in paid["events"]]==["customer-m100","adjuster-demo","finance-demo"]
    assert paid["claim"]["evaluation"]==first["claim"]["evaluation"]
    assert paid["workflow_contract_hash"]==WORKFLOW_HASH


@pytest.mark.parametrize("member,service,expected",[("M100","outpatient",90000),("M200","hospital",90000),("M400","dental",90000),("M500","vision",90000),("M600","hospital",90000),("M700","prescription",90000),("M800","medical",90000),("M900","outpatient",90000)])
def test_plan_specific_customer_submissions(workflow,member,service,expected):
    data=workflow.submit('customer-'+member.lower(),{**BASE,"member_id":member,"service":service})
    assert data["claim"]["evaluation"]["payout_cents"]==expected
    assert data["claim"]["status"]=="submitted"


@pytest.mark.sanity
def test_duplicate_and_replayed_payment_preserve_full_evidence(workflow):
    original=submit(workflow)
    with pytest.raises(WorkflowError) as duplicate:submit(workflow)
    assert duplicate.value.code=="DUPLICATE_CLAIM"
    assert workflow.get("customer-m100","CLM-100")==original
    workflow.transition("adjuster-demo","CLM-100",{"target":"approved"})
    paid=workflow.transition("finance-demo","CLM-100",{"target":"paid"})
    with pytest.raises(WorkflowError) as replay:workflow.transition("finance-demo","CLM-100",{"target":"paid"})
    assert replay.value.status==409
    assert workflow.get("auditor-demo","CLM-100")==paid


@pytest.mark.parametrize("actor,target",[("customer-m100","approved"),("customer-m200","paid"),("finance-demo","approved"),("adjuster-demo","paid"),("auditor-demo","approved"),("missing","paid")])
def test_forbidden_actions_preserve_status_revision_history_and_ledger(workflow,actor,target):
    original=submit(workflow)
    with pytest.raises(WorkflowError) as error:workflow.transition(actor,"CLM-100",{"target":target})
    assert error.value.status==403
    assert workflow.get("auditor-demo","CLM-100")==original


def test_finance_cannot_skip_adjuster_approval(workflow):
    original=submit(workflow)
    with pytest.raises(WorkflowError) as error:workflow.transition("finance-demo","CLM-100",{"target":"paid"})
    assert error.value.code=="INVALID_TRANSITION"
    assert workflow.get("auditor-demo","CLM-100")==original


def test_customer_cannot_read_or_submit_another_member(workflow):
    submit(workflow)
    with pytest.raises(WorkflowError) as error:workflow.get("customer-m200","CLM-100")
    assert error.value.status==403
    with pytest.raises(WorkflowError):workflow.submit("customer-m200",BASE)
    assert workflow.list("customer-m200")["claims"]==[]


@pytest.mark.parametrize("actor",["adjuster-demo","finance-demo","auditor-demo",None])
def test_only_known_customer_can_submit(workflow,actor):
    with pytest.raises(WorkflowError) as error:workflow.submit(actor,BASE)
    assert error.value.status==403
    assert workflow.list("auditor-demo")["claims"]==[]


@pytest.mark.parametrize("changes",[{"service":"dental"},{"in_network":False,"member_id":"M800"},{"authorized":False,"service":"hospital"}])
def test_denied_submission_does_not_reserve_id(workflow,changes):
    actor='customer-'+changes.get('member_id','M100').lower()
    with pytest.raises(WorkflowError) as error:workflow.submit(actor,{**BASE,**changes})
    assert error.value.status==422
    assert workflow.list("auditor-demo")["claims"]==[]
    assert submit(workflow)["claim"]["revision"]==1


def test_inactive_member_cannot_create_claim(workflow):
    with pytest.raises(WorkflowError) as error:workflow.submit("customer-m300",{**BASE,"member_id":"M300"})
    assert error.value.details["evaluation"]["reason"]=="INACTIVE_POLICY"
    assert workflow.list("auditor-demo")["claims"]==[]


@pytest.mark.parametrize("payload",[None,[],{}, {**BASE,"role":"finance"},{**BASE,"active":True},{**BASE,"plan_id":"medicare_a"},{**BASE,"claim_id":"../bad"},{**BASE,"claim_id":"ab"},{**BASE,"claim_id":"x"*49},{**BASE,"amount_cents":True}])
def test_bad_submission_contract_stores_nothing(workflow,payload):
    with pytest.raises(WorkflowError) as error:workflow.submit("customer-m100",payload)
    assert error.value.status==400
    assert workflow.list("auditor-demo")["claims"]==[]


@pytest.mark.parametrize("payload",[None,{}, {"target":"submitted"},{"target":"approved","role":"adjuster"},{"target":[]}])
def test_bad_transition_contract_preserves_evidence(workflow,payload):
    first=submit(workflow)
    with pytest.raises(WorkflowError) as error:workflow.transition("adjuster-demo","CLM-100",payload)
    assert error.value.status==400
    assert workflow.get("auditor-demo","CLM-100")==first


def test_reopen_database_preserves_committed_claim_and_history(workflow):
    first=submit(workflow)
    reopened=WorkflowService(ClaimStore(workflow.store.path))
    assert reopened.get("customer-m100","CLM-100")==first


def test_different_database_has_no_shared_records(workflow,tmp_path):
    submit(workflow)
    other=WorkflowService(ClaimStore(tmp_path/"other.sqlite"))
    assert other.list("auditor-demo")["claims"]==[]


def test_storage_failure_rolls_back_transition_ledger_and_event(workflow):
    submit(workflow)
    before=workflow.transition("adjuster-demo","CLM-100",{"target":"approved"})
    with workflow.store.transaction(write=True) as db:
        db.execute("CREATE TRIGGER inject_failure BEFORE INSERT ON payments BEGIN SELECT RAISE(ABORT,'test fault'); END")
    with pytest.raises(sqlite3.IntegrityError):workflow.transition("finance-demo","CLM-100",{"target":"paid"})
    assert workflow.get("auditor-demo","CLM-100")==before


def test_concurrent_duplicate_submissions_create_exactly_one_claim(workflow):
    barrier=threading.Barrier(2)
    def attempt():
        barrier.wait()
        try:submit(workflow);return 'created'
        except WorkflowError as error:return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
    assert sorted(results)==['DUPLICATE_CLAIM','created']
    evidence=workflow.get("auditor-demo","CLM-100")
    assert len(evidence["events"])==1
    assert len(workflow.list("auditor-demo")["claims"])==1


def test_concurrent_payments_record_exactly_one_ledger_entry(workflow):
    submit(workflow);workflow.transition("adjuster-demo","CLM-100",{"target":"approved"})
    barrier=threading.Barrier(2)
    def attempt():
        barrier.wait()
        try:workflow.transition("finance-demo","CLM-100",{"target":"paid"});return 'paid'
        except WorkflowError as error:return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
    assert sorted(results)==['INVALID_TRANSITION','paid']
    evidence=workflow.get("auditor-demo","CLM-100")
    assert evidence["claim"]["revision"]==3
    assert len(evidence["events"])==3
    with workflow.store.transaction() as db:assert db.execute('SELECT COUNT(*) FROM payments').fetchone()[0]==1


def test_zero_payout_is_a_valid_single_simulated_ledger_entry(workflow):
    submit(workflow,amount_cents=10000)
    workflow.transition("adjuster-demo","CLM-100",{"target":"approved"})
    paid=workflow.transition("finance-demo","CLM-100",{"target":"paid"})
    assert paid["payment"]["amount_cents"]==0


def test_sql_like_claim_id_is_rejected_and_fixture_tables_remain(workflow):
    with pytest.raises(WorkflowError):submit(workflow,claim_id="x'; DROP TABLE claims;--")
    assert submit(workflow)["claim"]["status"]=="submitted"


def test_transition_error_in_event_insert_rolls_back_created_payment(workflow):
    submit(workflow)
    before=workflow.transition("adjuster-demo","CLM-100",{"target":"approved"})
    with workflow.store.transaction(write=True) as db:
        db.execute("CREATE TRIGGER inject_event_failure BEFORE INSERT ON events WHEN NEW.to_status='paid' BEGIN SELECT RAISE(ABORT,'event fault'); END")
    with pytest.raises(sqlite3.IntegrityError):workflow.transition("finance-demo","CLM-100",{"target":"paid"})
    assert workflow.get("auditor-demo","CLM-100")==before


def test_sqlite_constraints_enforce_one_payment_even_outside_service(workflow):
    submit(workflow);workflow.transition("adjuster-demo","CLM-100",{"target":"approved"})
    workflow.transition("finance-demo","CLM-100",{"target":"paid"})
    with pytest.raises(sqlite3.IntegrityError):
        with workflow.store.transaction(write=True) as db:
            db.execute("INSERT INTO payments VALUES(?,?,?,?,?)",("CLM-100","SIM-OTHER",90000,"finance-demo","synthetic"))
    assert workflow.get("auditor-demo","CLM-100")["claim"]["revision"]==3


def test_repeat_approval_conflicts_without_an_extra_event(workflow):
    submit(workflow)
    before=workflow.transition("adjuster-demo","CLM-100",{"target":"approved"})
    with pytest.raises(WorkflowError) as error:workflow.transition("adjuster-demo","CLM-100",{"target":"approved"})
    assert error.value.status==409
    assert workflow.get("auditor-demo","CLM-100")==before


def test_duplicate_ids_are_global_even_across_members(workflow):
    submit(workflow)
    with pytest.raises(WorkflowError) as error:workflow.submit("customer-m200",{**BASE,"member_id":"M200"})
    assert error.value.code=="DUPLICATE_CLAIM"
    assert workflow.list("customer-m200")["claims"]==[]


def test_existing_id_conflicts_before_new_coverage_denial(workflow):
    before=submit(workflow)
    with pytest.raises(WorkflowError) as error:submit(workflow,service="dental")
    assert error.value.code=="DUPLICATE_CLAIM"
    assert error.value.status==409
    assert workflow.get("auditor-demo","CLM-100")==before


def test_fixture_members_actors_and_policies_are_consistent():
    from healthcare_quality.catalog import PLANS
    plan_ids={p["id"] for p in PLANS}
    assert len({m["id"] for m in MEMBERS})==len(MEMBERS)==9
    assert len({a["id"] for a in ACTORS})==len(ACTORS)==12
    assert {m["plan_id"] for m in MEMBERS}==plan_ids
    assert all(type(m["active"]) is bool for m in MEMBERS)
    assert {a["member_id"] for a in ACTORS if a["role"]=="customer"}=={m["id"] for m in MEMBERS}
