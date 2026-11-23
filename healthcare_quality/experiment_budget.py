"""Read-only planning for explicit bounded local model jobs."""
import statistics
from healthcare_quality.expectation_lab import selection
from healthcare_quality.ai_studio import StudioError
DEFAULT_SECONDS=180
MAX_SECONDS=300

def request(body):
 if not isinstance(body,dict):raise StudioError('INVALID_REQUEST','Provide an object')
 data=dict(body);seconds=data.pop('max_seconds',DEFAULT_SECONDS)
 if type(seconds) is not int or not 1<=seconds<=MAX_SECONDS:raise StudioError('INVALID_TIME_BUDGET','Choose integer max_seconds between1and300')
 return data,seconds

def estimate(body,records,cohort):
 data,seconds=request(body);chosen=selection(data,cohort);timings={}
 for record in records:
  for row in record['rows']:
   for call in row['calls']:
    ms=call.get('response',{}).get('latency_ms')
    if isinstance(ms,(int,float)) and not isinstance(ms,bool) and ms>0:timings.setdefault(row['model'],[]).append(ms/1000)
 per_model={m:statistics.median(timings[m]) if timings.get(m) else (90 if m=='qwen3.5:27b' else 15) for m in data['models']}
 each=chosen['request_budget']//len(data['models']);expected=round(sum(per_model.values())*each,1)
 return dict(request_budget=chosen['request_budget'],estimated_seconds=expected,max_seconds=seconds,estimate_fits_budget=expected<=seconds,per_model_seconds=per_model,estimate_basis='Recorded completed-request medians when available; otherwise conservative defaults. Not a completion guarantee.',budget_scope='From job admission; preflight separate. Late results fenced; backend cancellation best effort.')
