"""Read-only saved experiment display; production mutants run only in the offline CLI."""
from pathlib import Path
import json
from flask import jsonify
from tools.fingerprints import source_hash
ROOT=Path(__file__).resolve().parents[1]
def register(app):
 @app.get('/api/advanced/effectiveness')
 def effectiveness_evidence():
  p=ROOT/'artifacts/v6.11/effectiveness.json'
  if not p.exists():return jsonify(status='not_run',scope='Explicit offline experiment required; this endpoint never runs mutation or AI jobs')
  r=json.loads(p.read_text());r['matches_current_source']=r['source_hash']==source_hash();return jsonify(r)
