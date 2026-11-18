"""Explicit CLI-only OpenAI Responses integration. No web endpoint or automatic retry."""
import json
import time
import urllib.request
from healthcare_quality.api_budget import MODEL, MAX_OUTPUT, BudgetError

class OpenAIProvider:
    def __init__(self, key, budget, *, transport=None):
        if not key: raise ValueError('An explicitly configured OpenAI key is required')
        self._key, self.budget = key, budget
        self._transport = transport or urllib.request.urlopen

    def generate(self, prompt, schema):
        payload = {'model': MODEL, 'input': prompt, 'store': False, 'service_tier': 'default',
                   'reasoning': {'effort': 'low'}, 'max_output_tokens': MAX_OUTPUT,
                   'text': {'format': {'type': 'json_schema', 'name': 'healthcare_expectation',
                                       'strict': True, 'schema': schema}}}
        body = json.dumps(payload, ensure_ascii=False).encode()
        reservation = self.budget.reserve(body)
        request = urllib.request.Request('https://api.openai.com/v1/responses', data=body,
                    headers={'Authorization': 'Bearer '+self._key, 'Content-Type': 'application/json'})
        started = time.monotonic()
        try:
            with self._transport(request, timeout=90) as response:
                raw = response.read(262145)
            if len(raw) > 262144: raise ValueError('Oversized response')
            result = json.loads(raw)
            cost = self.budget.complete(reservation, result.get('usage'))
        except Exception as error:
            self.budget.uncertain(reservation)
            raise BudgetError('OpenAI request failed or charge is uncertain; stopped without retry ('+
                              type(error).__name__+').') from None
        texts = [part['text'] for item in result.get('output', []) if item.get('type') == 'message'
                 for part in item.get('content', []) if part.get('type') == 'output_text']
        return {'text': '\n'.join(texts), 'completed': result.get('status') == 'completed',
                'model': result.get('model', MODEL), 'response_id': result.get('id'),
                'usage': result['usage'], 'usage_estimate_usd': cost,
                'latency_ms': round((time.monotonic()-started)*1000, 2),
                'output_mode': 'OpenAI Responses strict JSON schema; store=false; no tools/retries'}
