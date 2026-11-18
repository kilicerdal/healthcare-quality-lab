"""Evidence-based suite recommendations and repeat-run instability; never deletes tests."""
def recommend(score):
    if score.get('state')!='scored':raise ValueError('Completed healthy-baseline score required')
    coverage={c['key']:set() for c in score['cases']}
    for f in score['faults']:
        for o in f.get('observations',[]):
            if o.get('status')=='detected' and o.get('first_mismatch') and o['case_key'] in coverage:coverage[o['case_key']].add(f['id'])
    uncovered=set().union(*coverage.values()) if coverage else set();target=set(uncovered);selected=[]
    while uncovered:
        best=min(coverage,key=lambda key:(-len(coverage[key]&uncovered),key))
        if not coverage[best]&uncovered:break
        selected.append(best);uncovered-=coverage[best]
    return dict(selected=selected,covered_profiles=sorted(target-uncovered),uncovered_profiles=sorted(uncovered),original_cases=len(coverage),suggested_cases=len(selected),scope='Greedy recommendation preserving observed seed detections only. Not a minimum proof, permission to remove tests, or general coverage guarantee.')
def instability(experiment):
    observations={}
    for run in experiment.get('runs',[]):
        if run.get('status') not in ('passed','failed'):continue
        for result in run.get('results',[]):observations.setdefault((run.get('source_hash'),run.get('contract_fingerprint'),run.get('revision'),run.get('transport','service'),result['case_id'],run.get('known_controlled_fault','none')),[]).append(result['passed'])
    return [dict(source_hash=k[0],contract=k[1],revision=k[2],transport=k[3],case_id=k[4],fault_profile=k[5],runs=len(v),mixed_outcomes=len(set(v))>1) for k,v in observations.items()]
