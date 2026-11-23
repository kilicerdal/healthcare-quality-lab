"""First attempts are complete stage pairs, never recovered/resumed passes."""
from collections import Counter
KIND='model_expectations_v86'
def classify(record,row):
 first=row.get('first',{});a=first.get('assessment') or {};calls=[c for c in row.get('calls',[]) if c['stage']=='first']
 resumed=record.get('resumed') is True or row.get('resumed') is True or record.get('first_attempt') is False
 if resumed:return 'resumed_pass' if a.get('eligible') else 'resumed_unpassed'
 if record.get('kind')!=KIND:return 'historical'
 if a.get('eligible'):
  n=len(first['answer']['observations']) if record['protocol']['selection']['strategy']=='stepwise' else 1
  phases=[c.get('generation',{}).get('phase') for c in calls]
  clean=phases==['pricing','lifecycle']*n and all(c['phase']=='response_frozen' and not c.get('response',{}).get('reused_frozen_model_response') for c in calls)
  return 'first_pass' if clean else 'nonfirst_pass'
 if not calls:return 'not_run'
 if any((c['phase']=='provider_error' and 'timeout' in c.get('error','').lower()) or (c['phase']=='interrupted' and record.get('stop_reason')=='time_budget') for c in calls):return 'timeout'
 if any(c['phase']=='provider_error' for c in calls):return 'provider_error'
 if any(c['phase']=='interrupted' for c in calls):return 'interrupted'
 if first.get('error') or a.get('schema_valid') is False:return 'invalid_output'
 if a:return 'incorrect_values'
 return 'in_progress' if record['state']=='running' else 'unassessed'

def scorecard(record):
 rows=record.get('rows',[]);outcomes=[dict(model=r['model'],task=r['task_id'],split=r['split'],outcome=classify(record,r)) for r in rows];counts=Counter(r['outcome'] for r in outcomes)
 complete=record.get('kind')==KIND and record['state']=='completed' and not any(k in counts for k in ('resumed_pass','resumed_unpassed','historical','not_run','in_progress','unassessed','interrupted'))
 return dict(policy='Two planned stages each once per requested scope; no retry/resume/reused response/reference repair. Self-review scores never replace original answers.',counts=dict(counts),planned=len(rows) if record.get('kind')==KIND or any(k.startswith('resumed') for k in counts) else 0,complete=complete,first_attempt_percent=round(100*counts['first_pass']/len(rows),2) if complete and rows else None,qualification=False,outcomes=outcomes,scope='Selected trials only; no general reliability/qualification claim. Historical and resumed outcomes remain separate.')
