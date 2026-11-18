/* Every scenario is explicit. Page load reads only; no paid provider endpoint exists. */
(()=>{'use strict';
const by=id=>document.getElementById(id);let saved=null;
const pretty=value=>JSON.stringify(value,null,2);
if(location.hash==='#proof')navigate('proof');
fetch('/api/showcase-lab').then(r=>{if(!r.ok)throw Error('Scenario catalog unavailable');return r.json();}).then(data=>{
  by('proof-scenarios').replaceChildren(...data.scenarios.map(item=>{const b=document.createElement('button');b.className='scenario';b.textContent=item.title;b.addEventListener('click',()=>run(item.id));return b;}));
  by('proof-status').textContent='Ready. Every run starts with fresh disposable state.';
}).catch(e=>by('proof-status').textContent=e.message);
async function run(scenario){
  const buttons=[...by('proof-scenarios').querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);saved=null;by('proof-export').disabled=true;
  by('proof-status').textContent='Executing the authored scenario…';by('proof-checks').textContent='Waiting for observed results…';by('proof-investigation').textContent='Waiting for evidence…';by('proof-raw').textContent='';by('proof-provenance').textContent='';
  try{
    const response=await fetch('/api/showcase-lab/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario})});
    if(!response.ok)throw Error('Scenario did not complete (HTTP '+response.status+'). No passing result is recorded.');
    const data=await response.json();saved=data;
    by('proof-status').textContent=data.title+' — '+data.status;
    const checks=document.createElement('table');checks.className='proof-check-table';
    const header=document.createElement('tr');for(const text of ['Business check','Expected','Observed']){const th=document.createElement('th');th.textContent=text;header.append(th);}checks.append(header);
    const compact=value=>Array.isArray(value)?value.join(', '):typeof value==='object'?JSON.stringify(value):String(value);
    for(const check of data.checks){const row=document.createElement('tr');for(const text of [(check.passed?'PASS · ':'FAIL · ')+check.label,compact(check.expected),compact(check.observed)]){const td=document.createElement('td');td.textContent=text;row.append(td);}checks.append(row);}
    by('proof-checks').replaceChildren(checks);
    by('proof-provenance').textContent=data.provenance+' '+data.method;
    const panels=[];
    const add=(title,value)=>{const d=document.createElement('div');const h=document.createElement('h3');h.textContent=title;const pre=document.createElement('pre');pre.textContent=pretty(value);d.append(h,pre);panels.push(d);};
    if(data.investigation){add('Frozen input',data.investigation.input);add('Written rule',data.investigation.rule);add('Proposed versus independent expectation',{proposed:data.investigation.proposed,expected:data.investigation.independent_expected,mismatches:data.investigation.mismatches});add('Observed seeded business defect',data.investigation.actual_fault_observation);add('Correction and explicit review',{corrected:data.investigation.corrected,approval:data.investigation.approval,next_step:data.investigation.next_step});}
    if(data.responses)add('Actual HTTP requests',data.responses.map(r=>({request_id:r.request_id,status:r.status,error:r.body.error||null})));
    if(data.state)add('Committed state',data.state);if(data.timeline)add('Committed event timeline',data.timeline);
    if(data.before)add('Interruption, rollback and retry',{before:data.before,after_interruption:data.after_interruption,after_retry:data.after_retry});
    if(data.change)add('Written requirement change',data.change);
    by('proof-investigation').replaceChildren(...panels);by('proof-raw').textContent=pretty(data);by('proof-export').disabled=false;
  }catch(e){by('proof-status').textContent=e.message;by('proof-checks').textContent='No successful evidence available.';}
  finally{buttons.forEach(b=>b.disabled=false);}
}
by('proof-export').addEventListener('click',()=>{if(!saved)return;const url=URL.createObjectURL(new Blob([pretty(saved)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='healthcare-'+saved.scenario+'.json';a.click();URL.revokeObjectURL(url);});
fetch('/api/showcase-lab/comparison').then(async r=>{if(r.status===404)return null;if(!r.ok)throw Error('Measurement unavailable');return r.json();}).then(data=>{
  if(!data){by('proof-comparison').textContent='No live comparison recorded yet. Use the explicit evaluation CLI; normal page loads do not call either model.';return;}
  const p=document.createElement('p');p.textContent=data.scope;const table=document.createElement('table');const head=document.createElement('tr');for(const value of ['Provider','Accepted / attempts','Rejected / errors','Median latency','API cost estimate']){const th=document.createElement('th');th.textContent=value;head.append(th);}table.append(head);
  for(const [name,result] of Object.entries(data.results)){const row=document.createElement('tr');for(const value of [name,result.accepted_for_review+' / '+result.attempts,result.rejected_or_error,result.median_latency_ms+' ms',result.usage_estimate_usd===null?'Not measured locally':'$'+result.usage_estimate_usd]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}table.append(row);}
  const label=document.createElement('label');label.htmlFor='proof-recorded-trial';label.textContent='Inspect a recorded provider output';const select=document.createElement('select');select.id='proof-recorded-trial';const trial=document.createElement('pre');
  for(const [index,row] of (data.rows||[]).entries()){const option=document.createElement('option');option.value=index;option.textContent=row.provider+' · '+row.scenario+' · trial '+row.trial+' · '+(row.assessment?.accepted_for_review?'eligible for review':'blocked / error');select.append(option);}
  const inspect=()=>{const row=data.rows?.[Number(select.value)];trial.textContent=row?pretty({provider:row.provider,scenario:row.scenario,trial:row.trial,input:row.input,expected:row.assessment?.independent_expected,proposed:row.assessment?.case?.steps?.[0]?.expect,calculation:row.assessment?.calculation,approval:row.assessment?.approval,error_type:row.error_type,raw_response:row.response?.text}):'No recorded trial available.';};select.addEventListener('change',inspect);inspect();
  const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Repeatability, protocol, failures and budget';const pre=document.createElement('pre');pre.textContent=pretty(data);details.append(summary,pre);by('proof-comparison').replaceChildren(p,table,label,select,trial,details);
}).catch(e=>by('proof-comparison').textContent=e.message);
})();
