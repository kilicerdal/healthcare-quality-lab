"""Run and record V5.4 evidence. A failed run never produces a passing dashboard."""
from datetime import datetime
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from tools.benchmark import benchmark
from tools.workflow_benchmark import workflow_benchmark
from healthcare_quality.workflow import WORKFLOW_HASH
from healthcare_quality.catalog import CONTRACT_HASH
from healthcare_quality import __version__
from tools.fingerprints import source_hash

ROOT=Path(__file__).resolve().parents[1]


def main():
    artifacts=ROOT/"artifacts"
    artifacts.mkdir(exist_ok=True)
    started=time.monotonic()
    before=source_hash()
    command=[sys.executable,"-m","pytest","-q","--junitxml",str(artifacts/"pytest-results.xml"),"--tracing","retain-on-failure","--screenshot","only-on-failure"]
    report_xml=artifacts/"pytest-results.xml"
    if report_xml.exists():report_xml.unlink()
    run=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print(run.stdout,end="")
    (artifacts/"pytest-output.txt").write_text(run.stdout)
    cases=list(ET.parse(artifacts/"pytest-results.xml").iter("testcase")) if (artifacts/"pytest-results.xml").exists() else []
    failed=sum(c.find("failure") is not None or c.find("error") is not None for c in cases)
    skipped=sum(c.find("skipped") is not None for c in cases)
    categories={category:sum(f"tests.{category}." in c.get("classname","") for c in cases) for category in ("unit","api","e2e")}
    defect_report=benchmark()
    (artifacts/"defect-benchmark.json").write_text(json.dumps(defect_report,indent=2)+"\n")
    workflow_report=workflow_benchmark()
    (artifacts/"workflow-benchmark.json").write_text(json.dumps(workflow_report,indent=2)+"\n")
    good=workflow_report["detected"]==workflow_report["total"] and not workflow_report["reference_failures"] and run.returncode==0 and bool(cases) and not skipped and source_hash()==before and not defect_report["reference_failures"] and defect_report["detected"]==defect_report["total"]
    now=datetime.now(ZoneInfo("America/New_York"))
    result={"status":"passed" if good else "failed","version":__version__,"recorded_at":now.isoformat(),"recorded_date":now.strftime("%Y-%m-%d"),
            "source_hash":before,"evaluation_contract_hash":CONTRACT_HASH,"workflow_contract_hash":WORKFLOW_HASH,"tests_total":len(cases),"tests_passed":len(cases)-failed-skipped,"tests_failed":failed,"tests_skipped":skipped,
            "categories":categories,"e2e_tests":categories["e2e"],"seeded_defects_detected":defect_report["detected"],"seeded_defects_total":defect_report["total"],
            "workflow_seeded_defects_detected":workflow_report["detected"],"workflow_seeded_defects_total":workflow_report["total"],"ai_case_language":"declarative DSL 1.0","live_model_in_core_tests":False,"reference_examples":defect_report["reference_cases"],"duration_seconds":round(time.monotonic()-started,2),
            "environment":{"python":platform.python_version(),"platform":platform.platform(),"pytest":version("pytest"),"playwright":version("playwright"),"flask":version("flask"),"waitress":version("waitress"),"browser":"Chromium only"},
            "command":"python -m tools.verify","subprocess_returncode":run.returncode,"ci_executed":os.environ.get("GITHUB_ACTIONS")=="true",
            "scope":"Local V5.4 regression: release integrity/activation/rollback, bootstrap, readiness/request tracing and evaluator/workflow tests, AI generation/review/runner controls, reference scoring/retrieval/comparison/investigation with offline provider doubles, real Chromium flows and retained fault experiments. Live Ollama demonstrations are recorded separately. Not production or Medicare compliance certification."}
    (artifacts/"verification.json").write_text(json.dumps(result,indent=2)+"\n")
    print(f"V5.4 verification: {result['status']} — {result['tests_passed']}/{result['tests_total']} passed; {result['e2e_tests']} browser checks; {defect_report['detected']}/{defect_report['total']} evaluation seeds and {workflow_report['detected']}/{workflow_report['total']} workflow seeds detected.")
    return 0 if good else 1

if __name__=="__main__":
    raise SystemExit(main())
