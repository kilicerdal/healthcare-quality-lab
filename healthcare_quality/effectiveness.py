"""Trusted production AST mutants, seeded generative properties and bounded reduction.
Only project-owned source is compiled. AI remains bounded declarative input data.
"""
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import ast,inspect,json,random,time
from healthcare_quality import benefits,benefit_claims
from healthcare_quality.advanced_runner import run
from healthcare_quality.advanced_schema import validate,semantic_key
from healthcare_quality.advanced_lab import check
from healthcare_quality.ai_schema import digest
from tools.fingerprints import source_hash

def variants():
    tree=ast.parse(inspect.getsource(benefits.calculate));result=[]
    for i,node in enumerate(ast.walk(tree)):
        if not (isinstance(node,ast.BinOp) or isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('min','max')):continue
        mutated=deepcopy(tree);target=list(ast.walk(mutated))[i];before=ast.unparse(target)
        if isinstance(target,ast.Call):target.func.id='max' if target.func.id=='min' else 'min'
        else:
            replacement={ast.Add:ast.Sub,ast.Sub:ast.Add,ast.Mult:ast.Add,ast.FloorDiv:ast.Mult}.get(type(target.op))
            if replacement is None:continue
            target.op=replacement()
        namespace=dict(benefits.calculate.__globals__);exec(compile(ast.fix_missing_locations(mutated),'<trusted-project-pricing-mutant>','exec'),namespace)
        result.append(dict(id='AST-'+str(i),before=before,after=ast.unparse(target),function=namespace['calculate']))
        if len(result)==40:break
    return result

@contextmanager
def pricing_variant(variant):
    with patch.object(benefit_claims,'calculate',variant['function']):yield

def suite_run(cases,variant=None):
    if not isinstance(cases,list) or not 1<=len(cases)<=16:raise ValueError('Use 1–16 bounded cases')
    for start in range(0,len(cases),3):validate(cases[start:start+3])
    for c in cases:
        try:
            if variant:
                with pricing_variant(variant):result=run([c])
            else:result=run([c])
        except Exception as e:return dict(passed=False,witness=dict(case_id=c['id'],kind='valid_input_exception',exception=type(e).__name__))
        if result['failed']:
            failed=result['results'][0]['steps'][-1]
            return dict(passed=False,witness=dict(case_id=c['id'],kind='assertion_mismatch',step=failed['step'],fields=[a['field'] for a in failed['assertions'] if not a['passed']]))
    return dict(passed=True,witness=None)

def properties(seed=611,examples=80,calculator=None):
    if type(seed) is not int or not 0<=seed<2**32 or type(examples) is not int or not 1<=examples<=200:raise ValueError('Bounded seed and 1–200 examples required')
    calculate=calculator or benefits.calculate;rng=random.Random(seed);plans=list(benefits.PLANS);checks=0
    for n in range(examples):
        plan=rng.choice(plans);policy=benefits.policy_for(rng.choice(['2026-03-01','2026-07-01','2027-01-01']),plan);amount=([1,5003,9999,10000,10001,10999,11000,11001][n] if n<8 else rng.randint(1,900000));other=rng.randrange(amount);service=rng.choice(benefits.PLANS[plan]['services']);line=dict(id='LINE-1',service=service,allowed_cents=amount,other_payer_cents=other)
        try:
            a=calculate(policy,[line]);t=a['totals']
            assert amount==sum(t[k] for k in ('payout_cents','member_cents','other_payer_cents','noncovered_cents'));checks+=1
            assert all(type(t[k]) is int and t[k]>=0 for k in ('payout_cents','member_cents','other_payer_cents','noncovered_cents'));checks+=1
            assert 0<=a['individual']['oop']<=policy['individual_oop'] and 0<=a['individual']['deductible']<=policy['individual_deductible'] and 0<=a['individual']['benefit']<=policy['annual_benefit'];checks+=1
            renamed=deepcopy(line);renamed['id']='RENAMED';b=calculate(policy,[renamed]);assert a['totals']==b['totals'] and a['individual']==b['individual'];checks+=1
            net=dict(line,allowed_cents=amount-other,other_payer_cents=0);c=calculate(policy,[net]);assert all(a['totals'][k]==c['totals'][k] for k in ('payout_cents','member_cents','noncovered_cents')) and a['individual']==c['individual'];checks+=1
        except Exception as e:return dict(passed=False,seed=seed,examples_attempted=n+1,checks_passed=checks,witness=dict(example=n,plan=plan,line=line,policy_id=policy['id'],exception=type(e).__name__),scope='Seeded generative/metamorphic properties; no expected values read from AI or the reference calculator')
    return dict(passed=True,seed=seed,examples_attempted=examples,checks_passed=checks,witness=None,scope='Five seeded generative/metamorphic relations per example; bounded examples, not exhaustive property proof or a Hypothesis run')

def lifecycle_properties():
    with TemporaryDirectory(prefix='hql-lifecycle-properties-') as tmp:
        s=benefit_claims.BenefitClaims(Path(tmp)/'benefits.sqlite');q=s.operate('customer-m100',dict(id='META-100',operation_key='meta-submit-100',member_id='M100',plan_id='commercial_ppo',service_date='2026-03-01',lines=[dict(id='LINE-1',service='medical',allowed_cents=97003)]),'submit')
        body=dict(operation_key='meta-payment-100',expected_revision=1);paid=s.operate('finance-demo',body,'pay',q['id']);replay=s.operate('finance-demo',body,'pay',q['id']);assert replay==paid
        current=s.get('customer-m100',q['id']);assert len(current['ledger'])==1 and current['revision']==2 and len(current['events'])==2
        reversed=s.operate('finance-demo',dict(operation_key='meta-reverse-100',expected_revision=2,note='Metamorphic reversal control'),'reverse',q['id']);assert sum(x['amount'] for x in reversed['ledger'])==0 and all(v==0 for v in reversed['current_member_accumulators'].values()) and all(v==0 for v in reversed['current_family_accumulators'].values())
        replay_after_reverse=s.operate('finance-demo',body,'pay',q['id']);assert replay_after_reverse==paid;after=s.get('customer-m100',q['id']);assert after==reversed
    return dict(passed=True,relations=['identical payment replay preserves original response','replay creates no ledger/history/revision change','reversal balances ledger and credits original accounts','old payment replay after reversal cannot resurrect settlement'],scope='Actual disposable SQLite lifecycle, no interactive claims or model calls')

def compare(suites,seed=611,examples=80):
    if not isinstance(suites,dict) or not 1<=len(suites)<=4:raise ValueError('Use 1–4 labeled suites')
    started=time.monotonic();mutants=variants();rows=[]
    for name,cases in suites.items():
        baseline=suite_run(cases);gate=all(check([c])['review_ready'] for c in cases)
        row=dict(name=name,case_count=len(cases),distinct_scenarios=len({semantic_key(c) for c in cases}),baseline=baseline,reference_matching=gate,scored=False,trials=[])
        if baseline['passed'] and gate:
            row['scored']=True
            for v in mutants:
                observed=suite_run(cases,v);row['trials'].append(dict(mutant=v['id'],detected=not observed['passed'],witness=observed['witness']))
            row.update(detected=sum(t['detected'] for t in row['trials']),total=len(mutants),survived=[t['mutant'] for t in row['trials'] if not t['detected']])
        else:row['reason']='Failing or reference-mismatching baseline is not credited as defect detection'
        rows.append(row)
    baseline_properties=properties(seed,examples);assert baseline_properties['passed'];property_trials=[]
    for v in mutants:
        result=properties(seed,examples,v['function']);property_trials.append(dict(mutant=v['id'],detected=not result['passed'],witness=result['witness']))
    authored_detected={t['mutant'] for row in rows if row['name'].startswith('authored_') and row['scored'] for t in row['trials'] if t['detected']}
    return dict(combined_authored_detection=dict(detected=len(authored_detected),total=len(mutants),scope='Union of disclosed authored suites; not AI-only coverage'),kind='test_effectiveness',source_hash=source_hash(),seed=seed,examples=examples,mutants=[{k:v[k] for k in ('id','before','after')} for v in mutants],suites=rows,properties=dict(baseline=baseline_properties,detected=sum(t['detected'] for t in property_trials),total=len(mutants),trials=property_trials),lifecycle=lifecycle_properties(),duration_seconds=round(time.monotonic()-started,2),live_model_calls=0,scope='Actual trusted arithmetic/min/max production-pricing mutations in disposable stores. Different suite sizes are disclosed, not an equal-budget AI superiority comparison. Surviving variants may be equivalent or expose gaps. Declarative historical AI cases are rechecked but never app-approved by this offline benchmark.')

def reduce_prefix(case,mutant_id,budget=16):
    if type(budget) is not int or not 1<=budget<=16:raise ValueError('Use 1–16 reduction attempts')
    v=next((x for x in variants() if x['id']==mutant_id),None)
    if v is None:raise ValueError('Unknown trusted mutant')
    validate([case])
    if not suite_run([case])['passed'] or suite_run([case],v)['passed']:raise ValueError('Need a healthy baseline and reproducible trusted-mutant failure')
    best=deepcopy(case);attempts=0
    for n in range(1,min(len(case['steps']),budget)+1):
        c=deepcopy(case);c['steps']=c['steps'][:n];attempts+=1
        try:validate([c])
        except Exception:continue
        if not suite_run([c],v)['passed']:best=c;break
    return dict(original_hash=digest(case),reduced_hash=digest(best),original_steps=len(case['steps']),reduced_steps=len(best['steps']),attempts=attempts,mutant=mutant_id,case=best,scope='Prefix-only reduction against a named trusted mutant. Original case and all retained inputs/expectations stay unchanged; not general delta debugging or monetary minimization.')
