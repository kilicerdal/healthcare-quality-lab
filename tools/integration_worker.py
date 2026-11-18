"""Trusted one-shot interruption worker used only by isolated integration rehearsals."""
import argparse,os
from healthcare_quality.benefit_claims import BenefitClaims
from healthcare_quality.integration import Coordinator

def main():
    p=argparse.ArgumentParser();p.add_argument('--state',required=True);p.add_argument('--benefits',required=True);p.add_argument('--url',required=True);p.add_argument('--key',required=True);a=p.parse_args()
    service=BenefitClaims(a.benefits);coordinator=Coordinator(a.state,service,a.url,os.environ['HQL_PEER_TOKEN'])
    try:coordinator.deliver(a.key,crash_after_local=True)
    except RuntimeError:os._exit(23)
    return 1
if __name__=='__main__':raise SystemExit(main())
