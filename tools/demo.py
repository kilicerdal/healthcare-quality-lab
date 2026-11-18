"""Start a reproducible synthetic demo in a NEW state directory. No model request."""
import argparse
from pathlib import Path
from healthcare_quality.workflow import ClaimStore, WorkflowService

def seed(directory):
    directory=Path(directory)
    if directory.exists() and any(directory.iterdir()):raise ValueError('Use a new empty state directory; existing data is never reset')
    directory.mkdir(parents=True,exist_ok=True)
    service=WorkflowService(ClaimStore(directory/'claims-v2.sqlite'))
    for name,amount in [('DEMO-READY',100000),('DEMO-PAID',137891)]:
        service.submit('customer-m100',{'claim_id':name,'member_id':'M100','service':'medical','amount_cents':amount})
        service.transition('adjuster-demo',name,{'target':'approved'})
        if name=='DEMO-PAID':service.transition('finance-demo',name,{'target':'paid'})
    return directory

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--state-dir',type=Path,required=True);parser.add_argument('--port',type=int,default=8895);args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Choose port 1024..65535')
    try:state=seed(args.state_dir)
    except ValueError as e:parser.error(str(e))
    from healthcare_quality.app import create_app
    from waitress import serve
    app=create_app({'DATABASE':str(state/'claims-v2.sqlite'),'AI_DATABASE':str(state/'ai-v3.sqlite')})
    print(f'Open http://127.0.0.1:{args.port}/#proof — authored disposable demo, no inference',flush=True)
    serve(app,host='127.0.0.1',port=args.port,threads=8)

if __name__=='__main__':main()
