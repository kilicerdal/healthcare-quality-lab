"""Run the standalone local showcase with Waitress on loopback only."""
import argparse,json,os
from pathlib import Path
from waitress import serve
from healthcare_quality.app import create_app
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--port",type=int,default=8895);parser.add_argument("--state-dir",type=Path,default=ROOT/".local")
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error("Choose a port between 1024 and 65535")
    state=args.state_dir.resolve();state.mkdir(parents=True,exist_ok=True)
    config={"DATABASE":str(state/"claims-v2.sqlite"),"AI_DATABASE":str(state/"ai-v3.sqlite")}
    if os.environ.get("HQL_IDENTITIES_FILE"):
        config.update(AUTH_MODE="shared",SECRET_KEY=os.environ.get("HQL_SESSION_SECRET"),IDENTITIES=json.loads(Path(os.environ["HQL_IDENTITIES_FILE"]).read_text()))
    app=create_app(config)
    print(f"Healthcare Quality Lab: http://127.0.0.1:{args.port}/#workbench",flush=True)
    serve(app,host="127.0.0.1",port=args.port,threads=8)
if __name__=="__main__":main()
