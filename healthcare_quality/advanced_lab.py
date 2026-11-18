"""Persisted advanced proposal generation, separate AI correction and explicit review."""
from copy import deepcopy
from datetime import datetime,timezone
import json,threading,time
from uuid import uuid4
from jsonschema import ValidationError
from healthcare_quality import operations
from healthcare_quality.ai_schema import MODELS,digest,json_loads
from healthcare_quality.ai_studio import ExperimentStore,StudioError
from healthcare_quality.advanced_schema import SCHEMA,DSL,RULES,validate,duplicate_groups,semantic_key,parse_model_json
from healthcare_quality.advanced_reference import assess
from healthcare_quality.advanced_runner import run
from healthcare_quality.benefits import FACTS
from tools.fingerprints import source_hash


def stamp():return datetime.now(timezone.utc).isoformat()
def contract_hash():return digest(dict(dsl=DSL,schema=SCHEMA,facts=FACTS))
def check(cases):
    try:
        validate(cases);duplicates=duplicate_groups(cases)
        rows=[dict(case_id=c['id'],**assess(c)) for c in cases]
        return dict(valid=True,matched=all(x['matched'] for x in rows),duplicates=duplicates,
                    review_ready=not duplicates and all(x['matched'] for x in rows),reference=rows)
    except (ValueError,TypeError,KeyError,ValidationError,RecursionError) as error:
        return dict(valid=False,matched=False,duplicates=[],review_ready=False,error=str(error)[:1500],reference=[])

def prompt_for(requirement):
    from healthcare_quality.advanced_reference import ACTORS,PLANS,FAMILY
    context=dict(dsl=DSL,rules=FACTS,plans=PLANS,actors=ACTORS,families=FAMILY)
    return ('Create one NEW advanced benefit test CASE as JSON matching the schema. '
            'Use only synthetic supplied facts, integer cents, exact fields, and no assumptions. '
            'Every successful step requires ALL observable fields. Submit success is 201, others 200. '
            'Calculate independent expected values, ledger amounts/counts, history/revision and member/family accumulators. '
            'Use a fresh case state. submit data has claim_id (not id), operation_key, member_id, plan_id, service_date, lines. '
            'pay/reverse/adjust/appeal/resolve data has claim_id,operation_key,expected_revision, and note where schema requires. '
            'Use unique operation keys except intentional identical replay. Allowed claim/line IDs have at least 3 characters. '
            'The first submit is revision 1/event count 1. Finance pays; adjuster adjusts/resolves; owner appeals. '
            'Other payer applies before deductible. Cap member charge at OOP. Annual benefit excess is noncovered. '
            'After adjustment retain paid state and add TWO ledger entries (credit old, debit new); reversal adds one credit. '
            'Appeal adds history without repricing; resolution reprices and returns adjudicated. '
            'After rejected writes on existing claims add an authorized unchanged-state readback. '
            'Do not call tools, generate code, invent endpoints or auto-approve. Maximum 6 steps for this request.\n'
            'FACTS: '+json.dumps(context,sort_keys=True)+'\nREQUIREMENT: '+requirement)

class AdvancedLab:
    def __init__(self,path,provider,generation_lock):
        from healthcare_quality.ollama_provider import OllamaProvider
        self.store=ExperimentStore(path);self.provider=OllamaProvider('advanced') if isinstance(provider,OllamaProvider) else provider;self.generation_lock=generation_lock
        self.recover()
    def recover(self):
        with self.store.transaction() as db:
            for row in db.execute('SELECT record_json FROM ai_experiments').fetchall():
                r=json_loads(row[0])
                if r['state']=='generating':
                    lease=db.execute('SELECT expires_at FROM studio_operations WHERE experiment_id=?',(r['id'],)).fetchone()
                    if not lease or lease[0]<=time.time():
                        r.update(state='interrupted',error='Generation lease expired. Raw evidence retained; explicit new request required.');db.execute('DELETE FROM studio_operations WHERE experiment_id=?',(r['id'],));self.store.save(db,r)
    def get(self,id):self.recover();return self.store.get(id)
    def _assessment(self,r,db=None):
        result=check(r['cases'])
        if r['provenance'].get('parent_id'):
            parent=self.store.load(db,r['provenance']['parent_id']) if db is not None else self.store.get(r['provenance']['parent_id'])
            preserved=result['valid'] and [semantic_key(c) for c in r['cases']]==[semantic_key(c) for c in parent['cases']]
            result['scenario_preserved']=preserved
            if not preserved:result.update(review_ready=False,matched=False,error='Correction changed scenario inputs/actions; proposal blocked')
        return result
    def records(self):
        self.recover()
        with self.store.transaction() as db:return [json_loads(x[0]) for x in db.execute('SELECT record_json FROM ai_experiments ORDER BY created_at DESC LIMIT 50')]
    def propose(self,cases,provenance=None):
        r=dict(id=uuid4().hex,created_at=stamp(),kind='advanced',state='proposed',revision=1,cases=deepcopy(cases),
               assessment=check(cases),contract_hash=contract_hash(),source_hash=source_hash(),
               provenance=provenance or dict(origin='authored'),raw=None,corrections=[],approval=None,runs=[])
        self.store.create(r);return r
    def generate(self,body,background=True):
        if not isinstance(body,dict) or set(body)!={'requirement','model'} or body['model'] not in MODELS or type(body['requirement']) is not str or not 10<=len(body['requirement'])<=2000:raise StudioError('INVALID_REQUEST','Provide a 10–2000 character requirement and installed allowlisted model')
        r=self.propose([],dict(origin='local_ollama',model=body['model'],requirement=body['requirement']))
        r.update(state='generating',prompt=prompt_for(body['requirement']),generation_schema=deepcopy(SCHEMA))
        with self.store.transaction() as db:token=operations.start(db,r,'advanced-generation',30);self.store.save(db,r)
        if background:threading.Thread(target=self._generate,args=(r,token),daemon=True).start()
        else:self._generate(r,token)
        return self.store.get(r['id'])
    def _generate(self,r,token):
        try:
            with operations.keepalive(self.store.path,token,30,5):
                if not self.generation_lock.acquire(False):raise StudioError('MODEL_BUSY','Another inference is active',429)
                try:r['raw']=self.provider.generate(r['provenance']['model'],r['prompt'],r['generation_schema'])
                finally:self.generation_lock.release()
                r['cases']=parse_model_json(r['raw']['text'])['cases'];r['assessment']=self._assessment(r);r['state']='proposed'
                if r['source_hash']!=source_hash() or r['contract_hash']!=contract_hash():
                    r.update(state='failed',error='Source/contract changed during generation; raw evidence retained');r['assessment'].update(review_ready=False,error='Source/contract changed')
        except Exception as e:
            r.update(state='failed',error=f'{type(e).__name__}: {e}'[:1500])
            if getattr(e,'raw_response',None) is not None:r['provider_error_raw']=e.raw_response
        finally:
            with self.store.transaction() as db:
                try:operations.finish(db,r,token)
                except operations.LeaseLost:return
                self.store.save(db,r)
    def review(self,id,reviewer,note,revision):
        if not isinstance(reviewer,str) or not 2<=len(reviewer)<=80 or not isinstance(note,str) or not 5<=len(note)<=1000:raise StudioError('INVALID_REVIEW','Reviewer and inspection note required')
        with self.store.transaction() as db:
            r=self.store.load(db,id)
            if r['revision']!=revision or r['state'] not in ('proposed','reviewed'):raise StudioError('REVISION_CONFLICT','Reload a reviewable proposal',409)
            if r['contract_hash']!=contract_hash() or r['source_hash']!=source_hash():raise StudioError('STALE_PROPOSAL','Regenerate against current source and contract',409)
            assessment=self._assessment(r,db)
            if not assessment['review_ready']:raise StudioError('REVIEW_BLOCKED','Independent oracle, schema and duplicate checks must pass',409)
            r['approval']=dict(reviewer=reviewer,note=note,at=stamp(),cases_hash=digest(r['cases']),contract_hash=contract_hash(),source_hash=source_hash());r['state']='reviewed';self.store.save(db,r);return r
    def execute(self,id,transport):
        with self.store.transaction() as db:
            r=self.store.load(db,id);a=r.get('approval')
            if not self._assessment(r,db)['review_ready'] or not a or a['cases_hash']!=digest(r['cases']) or a['contract_hash']!=contract_hash() or a['source_hash']!=source_hash():raise StudioError('APPROVAL_REQUIRED','Current snapshot-bound review required',409)
            revision=r['revision'];cases=deepcopy(r['cases'])
        result=run(cases,transport)
        with self.store.transaction() as db:
            current=self.store.load(db,id)
            if current['revision']!=revision or current.get('approval')!=a or a['source_hash']!=source_hash() or a['contract_hash']!=contract_hash():raise StudioError('STALE_RUN','Review changed while execution was running',409)
            current['runs'].append(dict(id=uuid4().hex,at=stamp(),**result));self.store.save(db,current);return current

    def correct(self,id,model,background=False):
        parent=self.get(id)
        if model not in MODELS or parent['state']!='proposed' or not parent['assessment']['valid']:
            raise StudioError('CORRECTION_BLOCKED','Correction requires a structurally valid, unapproved proposal and allowlisted model',409)
        if parent['source_hash']!=source_hash() or parent['contract_hash']!=contract_hash():raise StudioError('STALE_PROPOSAL','Regenerate against current source before correction',409)
        if parent['provenance'].get('reference_assisted'):raise StudioError('CORRECTION_LIMIT','Only one AI correction step is supported',409)
        r=self.propose([],dict(origin='local_ollama_corrected',model=model,parent_id=id,reference_assisted=True,requirement=parent['provenance'].get('requirement',parent['cases'][0]['title'])))
        r.update(state='generating',generation_schema=deepcopy(SCHEMA),prompt=prompt_for(r['provenance']['requirement'])+'\nCorrect ONLY the expected values in this original proposal. Preserve action order, actor and business inputs. Reference feedback is assistance, never raw model performance.\nORIGINAL: '+json.dumps(parent['cases'])+'\nREFERENCE FEEDBACK: '+json.dumps(parent['assessment']))
        with self.store.transaction() as db:
            token=operations.start(db,r,'advanced-correction',30);self.store.save(db,r)
            latest=self.store.load(db,id);latest['corrections'].append(r['id']);self.store.save(db,latest)
        if background:threading.Thread(target=self._generate,args=(r,token),daemon=True).start()
        else:self._generate(r,token)
        return self.store.get(r['id'])
    def score(self,id):
        r=self.execute(id,'service');baseline=r['runs'][-1]
        if baseline['failed']:raise StudioError('FAILING_BASELINE','A failing baseline cannot receive a sensitivity score',409)
        from healthcare_quality.advanced_runner import FAULTS
        trials=[dict(field=f,detected=bool(run(r['cases'],fault=f)['failed'])) for f in FAULTS]
        score=dict(at=stamp(),cases_hash=digest(r['cases']),source_hash=source_hash(),detected=sum(x['detected'] for x in trials),total=len(trials),trials=trials,scope='Bounded observable-contract mutants, not exhaustive application mutations or claims of general AI quality.')
        with self.store.transaction() as db:
            current=self.store.load(db,id)
            if current.get('approval')!=r['approval'] or current['approval']['source_hash']!=source_hash():raise StudioError('STALE_SCORE','Review/source changed during scoring',409)
            current.setdefault('scores',[]).append(score);self.store.save(db,current)
        return score
