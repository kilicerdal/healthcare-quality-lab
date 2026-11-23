"""Read-only saved evidence; loading or refreshing never runs a model or a fault."""
from pathlib import Path
from flask import jsonify,render_template
from healthcare_quality.reliability_evidence import read
ROOT=Path(__file__).resolve().parents[1]
def register(app):
 @app.get('/reliability')
 def reliability_page():return render_template('reliability.html')
 @app.get('/api/advanced/reliability-study')
 def reliability_saved():
  path=Path(app.config.get('RELIABILITY_EVIDENCE',ROOT/'artifacts/v8.7/dashboard.json'))
  if not path.is_file():return jsonify(status='not_recorded',message='No sealed study saved. Page load makes zero model calls.'),404
  try:return jsonify(read(path))
  except (ValueError,KeyError,TypeError):return jsonify(status='invalid_evidence',message='Evidence integrity validation failed; no scores displayed.'),409
