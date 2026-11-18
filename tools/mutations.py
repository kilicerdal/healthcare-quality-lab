"""Bounded AST mutation of trusted pure pricing code; never executes AI-generated code."""
import ast,copy,inspect,json,random,time
from healthcare_quality import benefits
from healthcare_quality.benefit_reference import price
from tools.fingerprints import source_hash

def benchmark():
    tree=ast.parse(inspect.getsource(benefits.calculate));sites=[i for i,n in enumerate(ast.walk(tree)) if isinstance(n,ast.BinOp) or isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('min','max')];faults=[]
    samples=[];rng=random.Random(61)
    for amount in [1,5000,5003,9999,10000,10001,50000,100000,210000,900000]+[rng.randint(1,900000) for _ in range(40)]:
        for service in ('medical','dental'):samples.append((amount,service,rng.randrange(amount+1)))
    policy=benefits.policy_for('2026-03-01','commercial_ppo')
    for index in sites[:40]:
        mutated=copy.deepcopy(tree);node=list(ast.walk(mutated))[index];original=ast.unparse(node)
        if isinstance(node,ast.Call):node.func.id='max' if node.func.id=='min' else 'min'
        else:
            replacement={ast.Add:ast.Sub,ast.Sub:ast.Add,ast.Mult:ast.Add,ast.FloorDiv:ast.Mult}.get(type(node.op))
            if not replacement:continue
            node.op=replacement()
        env=dict(benefits.calculate.__globals__);exec(compile(ast.fix_missing_locations(mutated),'<trusted-pricing-mutant>','exec'),env);killed=False;failure=None
        for amount,service,other in samples:
            lines=[dict(id='L1',service=service,allowed_cents=amount,other_payer_cents=other)];individual=dict(deductible=other%10001,oop=other%30001,benefit=other%200001);family={k:v*2 for k,v in individual.items()};family['deductible']=max(individual['deductible'],19999) if amount%2 else family['deductible'];family['oop']=max(individual['oop'],59999) if amount%3==0 else family['oop'];expected=price('2026-03-01','commercial_ppo',lines,individual,family)
            try:
                result=env['calculate'](policy,lines,individual,family)
                if result['allocation']!={k:expected['individual'][k]-individual[k] for k in individual} or result['individual']!=expected['individual'] or result['family']!=expected['family'] or any(result['totals'][k]!=expected[k] for k in ('payout_cents','member_cents','noncovered_cents')):killed=True;failure=dict(amount=amount,service=service,other_payer=other);break
            except Exception as e:killed=True;failure=dict(valid_input_exception=type(e).__name__);break
        faults.append(dict(site=index,original=original,mutated=ast.unparse(node),detected=killed,witness=failure))
    return dict(source_hash=source_hash(),total=len(faults),detected=sum(x['detected'] for x in faults),survived=[x['site'] for x in faults if not x['detected']],mutants=faults,scope='Bounded arithmetic/min/max AST mutations of trusted pricing code, tested against separate Fraction oracle. Survivors include potentially equivalent mutants; not exhaustive mutation coverage.')
if __name__=='__main__':print(json.dumps(benchmark(),indent=2))
