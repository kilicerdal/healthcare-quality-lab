"""Mapped scenario coverage, equivalence checks and bounded observed fault scoring.
No coverage is inferred from a model's prose or a mere rule citation.
"""
from copy import deepcopy
import json
import time
import re
from pathlib import Path
from uuid import uuid4
from jsonschema import validate
from healthcare_quality.ai_schema import ALL_RULES,MODELS,digest,contract_fingerprint,json_loads
from healthcare_quality.ai_studio import ExperimentStore,StudioError,checked_cases,now
from healthcare_quality.ai_runner import run_cases
from healthcare_quality.evaluation import signature
from healthcare_quality.assertion_quality import policy_fingerprint
from healthcare_quality import reference,operations,focused
from tools.fingerprints import source_hash

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'healthcare_quality/data/coverage_v55.json'
GAPS=[
    ('invalid-zero',['HC-001'],'Evaluate commercial_ppo medical amount_cents 0; assert 400 INVALID_REQUEST.'),
    ('inactive-uncovered',['HC-002','HC-003'],'Evaluate medicare_b dental amount_cents 100000 active false; assert inactive denial takes precedence.'),
    ('network-authorization',['HC-004','HC-005'],'Evaluate medicare_advantage hospital amount_cents 100000 in_network false authorized false; assert network denial precedes authorization.'),
    ('formulary',['HC-006'],'Evaluate medicare_d prescription amount_cents 100000 formulary false; assert NON_FORMULARY and zero payout.'),
    ('deductible-plus-one',['HC-007'],'Evaluate commercial_ppo medical amount_cents 10001; assert approved payout exactly 1 cent.'),
    ('cap-plus-one',['HC-007'],'Evaluate commercial_ppo medical amount_cents 210001; assert approved payout capped at 200000.'),
    ('ownership',['WF-001','WF-002'],'Submit an M100 medical claim as customer-m100, then reject customer-m200 read with 403; owner reads unchanged evidence.'),
    ('duplicate-readback',['WF-002','WF-005'],'Submit an M100 claim, repeat the same ID with 409 DUPLICATE_CLAIM, then owner reads unchanged full evidence.'),
    ('skip-approval',['WF-003','WF-005'],'Submit an M100 claim then finance attempts paid before approval, expect 409; owner reads unchanged full evidence.'),
    ('zero-payment',['HC-007','WF-002','WF-003','WF-004','WF-005'],'M100 medical amount 9999: submit, adjuster approve, finance pay, owner read. Assert payout 0 throughout, null payment before paid then payment 0; revisions/events 1,2,3,3.'),
    ('payment-replay',['WF-003','WF-004','WF-005'],'M100 medical amount 100000: submit, approve, pay, repeat paid expecting 409, then owner read unchanged payout/payment 90000 and revision/events 3.')]
PROFILES=[{'id':'eval-'+id,'family':'evaluate','defect':id,'rule_id':rule} for id,rule in [('eligibility','HC-002'),('coverage','HC-003'),('network','HC-004'),('authorization','HC-005'),('formulary','HC-006'),('deductible','HC-007'),('limit','HC-007')]]+[
    {'id':'workflow-'+id,'family':'workflow','defect':id,'rule_id':rule} for id,rule in [('ownership','WF-001'),('duplicate_replay','WF-002'),('skip_approval','WF-003'),('ledger_amount','WF-004'),('history_skip','WF-005')]]
SCOPE='Explicit authored inventory plus saved Studio proposals; not repository-wide pytest discovery, line/branch coverage, exhaustive mutation testing or real insurance certification.'

def fingerprints():return dict(source_hash=source_hash(),contract_fingerprint=contract_fingerprint(),reference_fingerprint=reference.fingerprint(),assertion_policy_fingerprint=policy_fingerprint())

def scenario_hash(case):
    normalized=signature(case)
    for step,canonical in zip(case['steps'],normalized):
        id=step['data'].get('claim_id')
        if id is not None and (not isinstance(id,str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,47}',id) is None):
            canonical['data']['claim_id']={'invalid_id_literal':id}
    return digest(normalized)
def assertion_hash(case):return digest([s['expect'] for s in case['steps']])

def duplicates(items):
    groups={}
    for item in items:
        if item['valid']:groups.setdefault(scenario_hash(item['case']),[]).append(item)
    result=[]
    for key,group in groups.items():
        if len(group)<2:continue
        equivalent={};conflicts=[]
        for item in group:equivalent.setdefault(assertion_hash(item['case']),[]).append(item['key'])
        for i,a in enumerate(group):
            for b in group[i+1:]:
                for index,(x,y) in enumerate(zip(a['case']['steps'],b['case']['steps']),1):
                    for field in x['expect'].keys() & y['expect'].keys():
                        if type(x['expect'][field]) is not type(y['expect'][field]) or x['expect'][field]!=y['expect'][field]:conflicts.append({'left':a['key'],'right':b['key'],'step':index,'field':field})
        result.append({'scenario_hash':key,'members':[i['key'] for i in group],'equivalent_assertion_groups':[v for v in equivalent.values() if len(v)>1],
                       'different_assertions':len(equivalent)>1,'conflicts':conflicts,'note':'Equivalent inputs do not imply redundant assertions. No cases or approvals are deleted.'})
    return result

def gap_matches(id,case):
    steps=case['steps']
    for i,s in enumerate(steps):
        d,e=s['data'],s['expect'];action=s['action']
        if action=='evaluate':
            if id=='invalid-zero' and d['amount_cents']==0 and e.get('error')=='INVALID_REQUEST':return True
            if id=='inactive-uncovered' and d.get('active') is False and d['service'] not in reference.PLANS.get(d['plan_id'],{}).get('services',[]) and e.get('reason')=='INACTIVE_POLICY':return True
            if id=='network-authorization' and d.get('in_network') is False and d.get('authorized') is False and d['service'] in reference.PLANS.get(d['plan_id'],{}).get('authorization_services',[]) and e.get('reason')=='OUT_OF_NETWORK':return True
            if id=='formulary' and e.get('reason')=='NON_FORMULARY':return True
            if id=='deductible-plus-one' and d['amount_cents']==10001 and e.get('payout_cents')==1:return True
            if id=='cap-plus-one' and d['amount_cents']==210001 and e.get('payout_cents')==200000:return True
        claim=d.get('claim_id')
        created_before=any(t['action']=='submit' and t['data'].get('claim_id')==claim and t['expect'].get('status')==201 for t in steps[:i])
        later=[t for t in steps[i+1:] if t['data'].get('claim_id')==claim]
        actor=reference.ACTORS.get(s['actor'],{})
        foreign_owner=actor.get('role')=='customer' and any(t['action']=='submit' and t['data'].get('claim_id')==claim and t['data'].get('member_id')!=actor.get('member_id') for t in steps[:i])
        paid_before=any(t['data'].get('claim_id')==claim and t['expect'].get('claim_status')=='paid' for t in steps[:i])
        unchanged=any(t['action']=='read' and t['expect'].get('status')==200 for t in later)
        if id=='ownership' and created_before and foreign_owner and action=='read' and e.get('error')=='FORBIDDEN' and unchanged:return True
        if id=='duplicate-readback' and e.get('error')=='DUPLICATE_CLAIM' and unchanged:return True
        if id=='skip-approval' and action=='transition' and d.get('target')=='paid' and e.get('error')=='INVALID_TRANSITION' and any(t['action']=='read' and t['expect'].get('claim_status')=='submitted' for t in later):return True
        if id=='zero-payment' and e.get('claim_status')=='paid' and e.get('payment_cents')==0 and e.get('payout_cents')==0 and any(t['action']=='read' and t['expect'].get('payment_cents')==0 for t in later):return True
        if id=='payment-replay' and paid_before and action=='transition' and d.get('target')=='paid' and e.get('error')=='INVALID_TRANSITION' and any(t['action']=='read' and t['expect'].get('claim_status')=='paid' and 'payment_cents' in t['expect'] for t in later):return True
    return False

class CoverageLab:
    def __init__(self,path,studio):self.store=ExperimentStore(path);self.studio=studio

    def inventory(self):
        items=[]
        for case in json.loads(CATALOG.read_text())['cases']:
            checked=checked_cases([case],case['rule_ids'])[0]
            items.append({**checked,'key':'authored:'+case['id'],'origin':'authored','eligible':checked['review_ready'],'experiment_id':None})
        with self.studio.store.transaction() as db:
            operations.recover(db)
            records=[json_loads(r['record_json']) for r in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 100')]
        for record in records:
            if not record['proposals']:continue
            try:approved={digest(c) for c in self.studio._approved_cases(record)}
            except StudioError:approved=set()
            for checked in checked_cases([p['case'] for p in record['proposals']],record['source_ids']):
                c=checked['case'];id=c.get('id') if isinstance(c,dict) and isinstance(c.get('id'),str) else 'malformed'
                items.append({**checked,'key':record['id']+':'+id,'origin':record.get('expectation_origin','original_ai'),'eligible':checked['valid'] and checked['hash'] in approved,'experiment_id':record['id'],'revision':record['revision'],'focused':bool(record.get('focused_source'))})
        return items

    def dashboard(self):
        items=self.inventory();eligible=[i for i in items if i['eligible']]
        unique={(scenario_hash(i['case']),assertion_hash(i['case'])) for i in eligible}
        gaps=[]
        for id,rules,brief in GAPS:
            matches=[i['key'] for i in eligible if gap_matches(id,i['case'])]
            gaps.append({'id':id,'rule_ids':rules,'brief':brief,'status':'represented' if matches else 'missing','case_keys':matches})
        rules=[]
        for id,rule in ALL_RULES.items():
            linked=[i for i in items if i['valid'] and id in i['case']['rule_ids']]
            rules.append({'id':id,'name':rule['name'],'linked_cases':[i['key'] for i in linked],'eligible_cases':[i['key'] for i in linked if i['eligible']],
                          'missing_gap_ids':[g['id'] for g in gaps if id in g['rule_ids'] and g['status']=='missing'],
                          'limitation':'Concurrency, reopen and storage rollback require authored tests outside sequential DSL; not measured here.' if id=='WF-006' else 'Linked cases and selected scenario evidence; not complete rule coverage.'})
        latest=next((r for r in self.records() if r['coverage_kind']=='defect_score' and r['state']=='scored'),None)
        observed=None
        if latest:
            latest=self.record(latest['id'])
            observed={'id':latest['id'],'current':latest['matches_current_implementation'] and latest['approval_snapshots_current'],'detected':latest['detected'],'applicable':latest['applicable'],
                      'detected_profile_ids':[f['id'] for f in latest['faults'] if f['status']=='detected'],'survived_profile_ids':[f['id'] for f in latest['faults'] if f['status']=='survived'],'cases':latest['unique_case_count'],'errors':latest.get('errors',0),'origins':{origin:sum(c['origin']==origin for c in latest['cases']) for origin in sorted({c['origin'] for c in latest['cases']})}}
        for rule in rules:
            rule['observed_detected_profiles']=[f['id'] for f in latest['faults'] if f['rule_id']==rule['id'] and f['status']=='detected'] if observed and observed['current'] else []
        attempt=next((r for r in self.records() if r['coverage_kind']=='defect_score'),None)
        result={'recorded_at':now(),**fingerprints(),'scope':SCOPE,'inventory_window':'All 32 explicit authored cases plus the latest 100 Studio experiments; older records are not scanned.',
                'counts':{'cases':len(items),'authored':sum(i['origin']=='authored' for i in items),'eligible':len(eligible),'unique_scenario_assertions':len(unique),'proposals_or_stale':sum(not i['eligible'] for i in items),'missing_gaps':sum(g['status']=='missing' for g in gaps)},
                'focused_metrics':self.focused_metrics(),'latest_attempt':{'id':attempt['id'],'state':attempt['state']} if attempt else None,'latest_score':observed,'rules':rules,'gaps':gaps,'duplicates':duplicates(items),'cases':items,'profiles':PROFILES}
        result['snapshot_hash']=digest({k:v for k,v in result.items() if k not in ('recorded_at','snapshot_hash')})
        return result

    def records(self):
        with self.store.transaction() as db:
            operations.recover(db)
            return [json_loads(r['record_json']) for r in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 30')]

    def record(self,id):
        record=self.store.get(id);record['matches_current_implementation']=all(record.get(k)==v for k,v in fingerprints().items())
        if record.get('coverage_kind')=='defect_score':
            current=True
            for snapshot in record['snapshots']:
                try:
                    experiment=self.studio.store.get(snapshot['id'])
                    self.studio._approved_cases(experiment)
                    current=current and experiment['revision']==snapshot['revision'] and experiment['approval']==snapshot['approval']
                except StudioError:current=False
            record['approval_snapshots_current']=current
        if record.get('coverage_kind')=='score_comparison':
            record['approval_snapshots_current']=all(self.record(record[k]).get('approval_snapshots_current',False) for k in ('before_id','after_id'))
        return record

    def focused_metrics(self):
        with self.studio.store.transaction() as db:
            operations.recover(db)
            records=[json_loads(r['record_json']) for r in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 100')]
        return focused.metrics(records)

    def close_gap(self,id,body):
        if not isinstance(body,dict) or set(body)!={'model'} or body['model'] not in MODELS:raise StudioError('INVALID_REQUEST','Provide an allowed local model')
        if id not in ('invalid-zero','payment-replay'):raise StudioError('INVALID_TARGET','Select the zero-amount or paid-replay scenario')
        snapshot=self.dashboard();gap=next(g for g in snapshot['gaps'] if g['id']==id)
        if gap['status']!='missing':raise StudioError('GAP_REPRESENTED','This scenario is already represented by eligible cases',409)
        provenance={'gap_source':{'gap_id':id,'dashboard_snapshot_hash':snapshot['snapshot_hash'],'mode':'explicit_gap_target'}}
        if id=='invalid-zero':return self.studio.generate_focused({'data':{'plan_id':'commercial_ppo','service':'medical','amount_cents':0},'model':body['model']},_provenance=provenance)
        claim='REPLAY-571';steps=[{'action':'submit','actor':'customer-m100','data':{'claim_id':claim,'member_id':'M100','service':'medical','amount_cents':134567}},
            {'action':'transition','actor':'adjuster-demo','data':{'claim_id':claim,'target':'approved'}},
            {'action':'transition','actor':'finance-demo','data':{'claim_id':claim,'target':'paid'}},
            {'action':'transition','actor':'finance-demo','data':{'claim_id':claim,'target':'paid'}},
            {'action':'read','actor':'customer-m100','data':{'claim_id':claim}}]
        rules=['HC-007','WF-002','WF-003','WF-004','WF-005']
        provenance['input_plan']={'id':id,'steps':steps,'source_ids':rules}
        brief='Create exactly one case with these exact ordered actions, actors and inputs: '+json.dumps(steps)+'. Cite exactly all selected rules. Step 1 returns 201 submitted, revision/events 1, payment null. Step 2 approves with revision/events 2 and null payment. Step 3 pays with revision/events 3 and payment equal to stored payout. Step 4 is a PAID replay: 409 INVALID_TRANSITION; no state or money fields on its error response. Step 5 owner reads unchanged paid revision/events 3 and the original payment. Assert all six success fields on steps 1,2,3,5. Calculate integer payout from written deductible and cap; no repeated payment, extra event or revision.'
        r=self.studio.generate({'requirement':brief,'source_ids':rules,'model':body['model'],'strategy':'assertions-v2','count':1},_provenance=provenance)
        return self.studio.view(r['id'])

    def assemble_evaluators(self,body):
        from healthcare_quality.ai_schema import validate_cases
        from healthcare_quality import __version__
        if not isinstance(body,dict) or set(body)!={'sources','reviewer_label','review_note'} or not isinstance(body['sources'],list) or not 1<=len(body['sources'])<=8:raise StudioError('INVALID_REQUEST','Select 1–8 reviewed focused sources and provide reviewer label/note')
        self.studio._reviewer(body);snapshots=[];steps=[];rules=set();assumptions=[];seen=set();origins=[];base=None
        with self.studio.store.transaction() as db:
            operations.recover(db)
            for selection in body['sources']:
                if not isinstance(selection,dict) or set(selection)!={'id','expected_revision'} or not isinstance(selection['id'],str) or selection['id'] in seen:raise StudioError('INVALID_REQUEST','Select unique focused experiment IDs with revisions')
                seen.add(selection['id']);r=self.studio.store.load(db,selection['id']);self.studio._revision(r,selection);cases=self.studio._approved_cases(r)
                if not r.get('focused_source') or len(cases)!=1 or len(cases[0]['steps'])!=1:raise StudioError('INVALID_ASSEMBLY','Assembly accepts reviewed single-request focused evaluators only',409)
                case=cases[0];fingerprint=(scenario_hash(case),assertion_hash(case))
                if any(s['scenario_assertion']==list(fingerprint) for s in snapshots):raise StudioError('DUPLICATE_ASSEMBLY','Equivalent input/assertion sources cannot inflate an assembly',409)
                steps.extend(deepcopy(case['steps']));rules.update(case['rule_ids']);origins.append(r.get('expectation_origin','original_ai'));base=base or deepcopy(r)
                for assumption in case['assumptions']:
                    if assumption not in assumptions:assumptions.append(assumption)
                snapshots.append({'id':r['id'],'revision':r['revision'],'case':deepcopy(case),'approval':deepcopy(r['approval']),'origin':origins[-1],'focused_source':deepcopy(r['focused_source']),'assessment':deepcopy(r['generation_assessment']),'scenario_assertion':list(fingerprint)})
            if len(rules)>6:raise StudioError('ASSEMBLY_BUDGET','An assembled DSL case supports at most six source rules; split this selection',409)
            if len(assumptions)>4:assumptions=['Source assumptions are retained verbatim in assembly_sources. Inspect every frozen source case before approving this assembled suite.']
            case={'id':'AI-ASSEMBLED-'+uuid4().hex[:12],'title':'Assembled reviewed focused evaluator suite','rule_ids':sorted(rules),'rationale':'Exact input/expectation copies from individually reviewed focused model drafts; no recalculation or model request during assembly.','assumptions':assumptions,'steps':steps}
            checked=checked_cases([case],sorted(rules))
            if not checked[0]['review_ready']:raise StudioError('INVALID_ASSEMBLY','Copied assembly does not satisfy current case/reference checks',409)
            for key in ('focused_source','generation_assessment','focused_validation','survivor_source','gap_source','input_plan','correction_of','reference_assisted_of','retry_of','correction_snapshot','correction_attempt','correction_root_id','operation','interruption','pending_run','approval_matches_focus','survivor_sequence_matches','input_plan_matches','assembly_sources','assembled_from'):base.pop(key,None)
            origin='assembled_ai' if all(o=='original_ai' for o in origins) else 'assembled_ai_corrected' if all(o in ('original_ai','reference_guided_ai') for o in origins) else 'assembled_assisted'
            base.update(id=uuid4().hex,created_at=now(),version=__version__,requirement='Explicit assembly of reviewed focused evaluators',source_ids=sorted(rules),source_rules=[ALL_RULES[id] for id in sorted(rules)],requested_count=1,state='proposed',revision=1,proposals=checked,approved_ids=[],approval=None,runs=[],raw_generation=None,generation_error=None,generation_schema_issues=[],generation_schema_version='focused-assembly-v1',generation_schema_hash=None,expectation_origin=origin,assembly_sources=snapshots,
                        prompt='No model request. Frozen reviewed input and expectation snapshots copied verbatim.',prompt_hash=digest(snapshots),history=[{'event':'focused_sources_assembled','at':now(),'reviewer_label':body['reviewer_label'],'note':body['review_note'],'scope':'Assembly is not approval. Review this new suite before execution.'}])
            db.execute('INSERT INTO ai_experiments VALUES(?,?,?)',(base['id'],base['created_at'],json.dumps(base,allow_nan=False)))
        return self.studio.view(base['id'])

    def survivor_plan(self,id,variant=False):
        from healthcare_quality.survivors import generation_groups,VERSION
        score=self.record(id)
        if score.get('coverage_kind')!='defect_score' or score['state']!='scored' or score.get('errors'):raise StudioError('INVALID_SCORE','Start with an error-free healthy-baseline score',409)
        if not score['matches_current_implementation'] or not score['approval_snapshots_current']:raise StudioError('STALE_SCORE','Rescore current reviewed cases before generating survivor targets',409)
        survivors=[f['id'] for f in score['faults'] if f['status']=='survived']
        plan={'score_id':id,'score_hash':digest({k:v for k,v in score.items() if k not in ('matches_current_implementation','approval_snapshots_current')}),
              'version':VERSION,'survivor_ids':survivors,'groups':generation_groups(survivors,variant),**fingerprints(),
              'scope':'Authored input/action plans targeting known surviving seeds. The model generates expectations; no automatic review or execution. Variants are development examples, not holdouts.'}
        plan['plan_hash']=digest(plan)
        return plan

    def generate_survivors(self,id,body):
        from healthcare_quality.survivors import group_match
        if not isinstance(body,dict) or set(body)!={'group_id','plan_hash','model','variant'} or type(body['variant']) is not bool or body['model'] not in MODELS:raise StudioError('INVALID_REQUEST','Provide group_id, plan_hash, allowed model and boolean variant')
        plan=self.survivor_plan(id,body['variant'])
        if body['plan_hash']!=plan['plan_hash']:raise StudioError('STALE_PLAN','Reload and inspect the current survivor plan',409)
        group=next((g for g in plan['groups'] if g['id']==body['group_id']),None)
        if group is None:raise StudioError('INVALID_TARGET','Choose a group with surviving faults',409)
        brief=('Create exactly ONE case containing EXACTLY these ordered actions, actors and input data: '+json.dumps(group['steps'])+
               '. Valid claim IDs may be consistently renamed; preserve identity relationships. Cite EXACTLY all selected rule IDs: '+json.dumps(group['source_ids'])+
               '. Include complete independent expected observations. Evaluate denials use status 200, denied reason and payout zero. Every successful workflow action asserts all six fields. Rejections assert only returned error/status, then the specified unchanged readback. Reads/rejections add no event. Amounts and payments are integer cents. Do not substitute different inputs or omit steps. Purpose: '+group['purpose']+' Written-rule outcome guidance: '+json.dumps(group['outcome_guidance']))
        provenance={'survivor_source':{'score_id':id,'plan_hash':plan['plan_hash'],'group':group}}
        proposal=self.studio.generate({'requirement':brief,'source_ids':group['source_ids'],'model':body['model'],'strategy':'oracle-check-v2','count':1},_provenance=provenance)
        return self.studio.view(proposal['id'])

    def compare(self,body):
        from healthcare_quality.survivors import compare
        if not isinstance(body,dict) or set(body)!={'before_id','after_id'} or any(not isinstance(v,str) for v in body.values()):raise StudioError('INVALID_REQUEST','Provide before_id and after_id only')
        before=self.record(body['before_id']);after=self.record(body['after_id']);result=compare(before,after)
        result.update(id=uuid4().hex,created_at=now(),coverage_kind='score_comparison',state='compared',revision=1,
                      **{k:before[k] for k in fingerprints()},snapshots_current=before['approval_snapshots_current'] and after['approval_snapshots_current'])
        self.store.create(result)
        return result

    def _operate(self,record,kind,work):
        record.update(created_at=now(),revision=1,state='generating' if kind=='generation' else 'running',proposals=[],approved_ids=[],approval=None,history=[],runs=[])
        with self.store.transaction() as db:
            operations.recover(db);token=operations.start(db,record,kind,30)
            db.execute('INSERT INTO ai_experiments VALUES(?,?,?)',(record['id'],record['created_at'],json.dumps(record,allow_nan=False)))
        with operations.keepalive(self.store.path,token,30,5):
            try:updates=work(record)
            except Exception as error:updates={'state':'failed','error':f'{type(error).__name__}: {error}'[:1000]}
            with self.store.transaction() as db:
                operations.recover(db);current=self.store.load(db,record['id'])
                try:operations.finish(db,current,token)
                except operations.LeaseLost as error:raise StudioError('OPERATION_LOST',str(error),409) from error
                current.update(updates);current['finished_at']=now();self.store.save(db,current)
        return current

    def analyze(self,body):
        if not isinstance(body,dict) or set(body)!={'model'} or body['model'] not in MODELS:raise StudioError('INVALID_REQUEST','Provide one allowed local model')
        dashboard=self.dashboard();missing=[g for g in dashboard['gaps'] if g['status']=='missing']
        if not missing:raise StudioError('NO_GAPS','No missing scenarios in the defined taxonomy; this is not complete contract coverage',409)
        if not self.studio.generation_lock.acquire(False):raise StudioError('MODEL_BUSY','Another local model request is active',429)
        try:
            schema={'type':'object','additionalProperties':False,'required':['suggestions'],'properties':{'suggestions':{'type':'array','minItems':1,'maxItems':3,'items':{'type':'object','additionalProperties':False,'required':['gap_id','explanation','brief'],'properties':{'gap_id':{'enum':[g['id'] for g in missing]},'explanation':{'type':'string','minLength':5,'maxLength':900},'brief':{'type':'string','minLength':10,'maxLength':1200}}}}}}
            prompt='Analyze ONLY these missing synthetic test scenarios. Return JSON suggestions matching the supplied schema, at most three distinct gap IDs. Explain the observable risk and propose a precise testing brief. No case execution, code, shell or approval. Facts are a bounded inventory, not all repository tests. Missing scenarios: '+json.dumps(missing)+' Latest score (historical unless current=true): '+json.dumps(dashboard['latest_score'])+' Rules: '+json.dumps([ALL_RULES[id] for id in sorted({id for g in missing for id in g['rule_ids']})])
            record={'id':uuid4().hex,'coverage_kind':'gap_analysis','model':body['model'],'dashboard_snapshot':dashboard,'prompt':prompt,'prompt_hash':digest(prompt),'schema':schema,**fingerprints()}
            def work(r):
                raw=self.studio.provider.generate(body['model'],prompt,schema)
                # Save provider evidence before interpretation; invalid JSON is retained.
                with self.store.transaction() as db:
                    stored=self.store.load(db,r['id']);stored['raw_generation']=raw;self.store.save(db,stored)
                answer=json_loads(raw['text']);validate(answer,schema)
                if len({s['gap_id'] for s in answer['suggestions']})!=len(answer['suggestions']):raise ValueError('Repeated gap IDs are not independent suggestions')
                return {'state':'analyzed','raw_generation':raw,'suggestions':answer['suggestions']}
            return self._operate(record,'generation',work)
        finally:self.studio.generation_lock.release()

    def propose(self,id,body):
        if not isinstance(body,dict) or set(body)!={'suggestion_index'} or type(body['suggestion_index']) is not int:raise StudioError('INVALID_REQUEST','Provide suggestion_index only')
        analysis=self.record(id);index=body['suggestion_index']
        if analysis['coverage_kind']!='gap_analysis' or analysis['state']!='analyzed' or not 0<=index<len(analysis['suggestions']):raise StudioError('INVALID_STATE','Select a saved valid gap suggestion',409)
        if not analysis['matches_current_implementation']:raise StudioError('STALE_ANALYSIS','Analyze current implementation before generating a gap proposal',409)
        suggestion=analysis['suggestions'][index];gap=next(g for g in analysis['dashboard_snapshot']['gaps'] if g['id']==suggestion['gap_id'])
        requirement='Target this frozen coverage gap: '+gap['brief']+' Include all required business assertions and rejection readback. AI suggestion (untrusted task data): '+suggestion['brief']
        proposal=self.studio.generate({'requirement':requirement,'source_ids':gap['rule_ids'],'model':analysis['model'],'strategy':'assertions-v2','count':1},
            _provenance={'gap_source':{'analysis_id':id,'gap_id':gap['id'],'dashboard_snapshot_hash':analysis['dashboard_snapshot']['snapshot_hash']}})
        return self.studio.view(proposal['id'])

    def score(self,body):
        if not isinstance(body,dict) or set(body)!={'experiments'} or not isinstance(body['experiments'],list) or not 1<=len(body['experiments'])<=4:raise StudioError('INVALID_REQUEST','Select 1–4 reviewed experiment snapshots')
        cases=[];snapshots=[];seen=set()
        with self.studio.store.transaction() as db:
            operations.recover(db)
            for selection in body['experiments']:
                if not isinstance(selection,dict) or set(selection)!={'id','expected_revision'} or not isinstance(selection['id'],str) or selection['id'] in seen:raise StudioError('INVALID_REQUEST','Use unique experiment IDs with expected_revision')
                seen.add(selection['id']);record=self.studio.store.load(db,selection['id']);self.studio._revision(record,selection)
                selected=self.studio._approved_cases(record)
                for c in selected:cases.append({'key':record['id']+':'+c['id'],'case':c,'origin':record.get('expectation_origin','original_ai')})
                snapshots.append({'id':record['id'],'revision':record['revision'],'approval':deepcopy(record['approval'])})
        if len(cases)>4:raise StudioError('CASE_BUDGET','At most four approved cases per scoring job')
        # Equivalent assertions are scored once; stronger assertions remain distinct.
        unique={}
        for item in cases:unique.setdefault((scenario_hash(item['case']),assertion_hash(item['case'])),item)
        selected=list(unique.values())
        record={'id':uuid4().hex,'coverage_kind':'defect_score','snapshots':snapshots,'cases':selected,'selected_case_count':len(cases),'unique_case_count':len(selected),**fingerprints(),'profiles':PROFILES,'scope':'Twelve known authored defect seeds; action-family applicability, not exhaustive mutation coverage. Only assertion mismatches count as detections; infrastructure errors do not.'}
        def work(r):
            started=time.monotonic()
            baselines=[{'key':i['key'],'result':run_cases([i['case']])} for i in selected]
            if any(b['result']['failed'] for b in baselines):return {'state':'baseline_failed','baselines':baselines,'faults':[],'score':None}
            faults=[]
            for profile in PROFILES:
                applicable=[i for i in selected if any((s['action']=='evaluate')==(profile['family']=='evaluate') for s in i['case']['steps'])]
                observations=[]
                for item in applicable:
                    if time.monotonic()-started>30:raise TimeoutError('Scoring time budget exhausted; no numeric score recorded')
                    result=run_cases([item['case']],**({'evaluation_defect':profile['defect']} if profile['family']=='evaluate' else {'workflow_defect':profile['defect']}))
                    error=any(c['execution_error'] for c in result['results'])
                    mismatch=next(({'step':s['number'],'field':a['field'],'expected':a['expected'],'observed':a['observed'],'rule_id':profile['rule_id']} for c in result['results'] for s in c['steps'] for a in s['assertions'] if not a['passed']),None)
                    observations.append({'case_key':item['key'],'status':'error' if error else 'detected' if mismatch else 'survived','first_mismatch':mismatch,'result':result})
                status='not_applicable' if not observations else 'error' if any(o['status']=='error' for o in observations) else 'detected' if any(o['status']=='detected' for o in observations) else 'survived'
                faults.append({**profile,'status':status,'observations':observations})
            applicable=sum(f['status']!='not_applicable' for f in faults);errors=sum(f['status']=='error' for f in faults);detected=sum(f['status']=='detected' for f in faults)
            return {'state':'incomplete' if errors else 'scored','baselines':baselines,'faults':faults,'detected':detected,'applicable':applicable,'errors':errors,'score':None if errors or not applicable else round(detected/applicable,4),'budget':{'cases':4,'profiles':12,'maximum_case_runs':52}}
        return self._operate(record,'execution',work)
