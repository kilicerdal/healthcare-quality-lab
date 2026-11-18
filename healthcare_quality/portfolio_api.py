from pathlib import Path
import json
from flask import jsonify
from healthcare_quality.portfolio import overview
from healthcare_quality.ai_studio import StudioError

def register(app,body):
 @app.get('/api/advanced/portfolio')
 def portfolio_overview():return jsonify(overview())
 @app.post('/api/advanced/portfolio/control')
 def portfolio_control():
  if body()!={}:raise StudioError('INVALID_REQUEST','Provide an empty object')
  case=json.loads((Path(__file__).with_name('data')/'advanced_cases_v63.json').read_text())['cases'][0]
  return jsonify(app.extensions['advanced'].propose([case],dict(origin='authored_v7_showcase_control',live_inference=False,label='Authored control; inspect and review separately before execution'))),201
