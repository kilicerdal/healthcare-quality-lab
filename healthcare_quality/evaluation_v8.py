"""Larger frozen inputs, partitioned by scenario families to limit split leakage."""
from healthcare_quality.coverage_packs import plan_for,journeys
from healthcare_quality.ai_schema import digest

def cohort():
 tasks=[]
 for i,pid in enumerate(('commercial_ppo','medicare_b','dental','vision','medicare_a','medicare_advantage','medicare_d','commercial_hmo')):
  for j,variant in enumerate(('covered','noncovered','deductible')):
   tasks.append(dict(id=f'EV8-{i*3+j+1:02}',split='development' if i<4 else 'reserved_until_exposed',family=pid,plan=plan_for(pid,variant,i*3+j+80)))
 for i,p in enumerate(journeys()):tasks.append(dict(id=f'EV8-J{i+1}',split='reserved_until_exposed',family='lifecycle',plan=p))
 return dict(version='evaluation-v8-1',tasks=tasks,hash=digest(tasks),scope='Authored fixed plans; held-out families are locally reserved until a real request is recorded. No claim of globally unseen model data.')
def matrix(tasks,models,prompts,repeats=2):
 if type(repeats) is not int or not 1<=repeats<=3:raise ValueError('Choose 1–3 repeats')
 known={t['id'] for t in cohort()['tasks']}
 from healthcare_quality.ai_schema import MODELS
 from healthcare_quality.test_design import PROMPTS
 for values,allowed in ((tasks,known),(models,MODELS),(prompts,PROMPTS)):
  if not values or len(set(values))!=len(values) or any(v not in allowed for v in values):raise ValueError('Select unique known matrix values')
 count=len(tasks)*len(models)*len(prompts)*repeats
 if count>24:raise ValueError('At most 24 model requests per explicit batch')
 return dict(tasks=tasks,models=models,prompts=prompts,repeats=repeats,request_budget=count,cohort_hash=cohort()['hash'],correction_budget=0)
