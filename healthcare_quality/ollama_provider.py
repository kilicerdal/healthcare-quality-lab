"""Fixed-loopback provider. No cloud fallback, model pulls, shell or tool access."""
import json
import time
import urllib.request
from healthcare_quality.ai_schema import MODELS,json_loads

ENDPOINT="http://127.0.0.1:11434"
SETTINGS={"temperature":0,"seed":7,"num_predict":2600,"num_ctx":12288}
MAX_RESPONSE_BYTES=262144


class ProviderError(ValueError):
    def __init__(self,message,raw_response=None):
        super().__init__(message)
        self.raw_response=raw_response


class OllamaProvider:
    def __init__(self,profile='legacy'):
        if profile not in ('legacy','advanced'):raise ValueError('Unknown fixed local inference profile')
        self.settings=dict(SETTINGS) if profile=='legacy' else dict(temperature=0,seed=7,num_predict=6000,num_ctx=16384)
        self.timeout=90 if profile=='legacy' else 240
        self.profile=profile
    def status(self):
        try:
            with urllib.request.urlopen(ENDPOINT+"/api/tags",timeout=3) as response:
                raw=response.read(65537)
            if len(raw)>65536:raise ValueError("Oversized model list")
            models=json_loads(raw).get("models",[])
            available=[{"name":m["name"],"digest":m.get("digest")} for m in models if m.get("name") in MODELS]
            return {"available":bool(available),"models":available,"allowed_models":list(MODELS),"endpoint":ENDPOINT,"mode":"local Ollama only"}
        except Exception as error:
            return {"available":False,"models":[],"allowed_models":list(MODELS),"endpoint":ENDPOINT,"error":type(error).__name__}

    def generate(self,model,prompt,schema):
        if model not in MODELS:raise ProviderError("Model is outside the local allowlist")
        # The installed 27B runtime rejects constrained format with HTTP 501.
        # Select this mode explicitly by model; never retry silently or swap models.
        mode="prompt-json-validated" if model=="qwen3.5:27b" else "schema-constrained"
        body={"model":model,"prompt":prompt,"stream":False,"options":self.settings}
        if mode=="prompt-json-validated":
            body.update(think=getattr(self,'reasoning_enabled',False),prompt=prompt+"\nOUTPUT JSON SCHEMA (return exactly one matching JSON object, no markdown): "+json.dumps(schema))
        else:body["format"]=schema
        request=urllib.request.Request(ENDPOINT+"/api/generate",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
        started=time.monotonic()
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response:
                raw=response.read(MAX_RESPONSE_BYTES+1)
            if len(raw)>MAX_RESPONSE_BYTES:raise ProviderError("Model envelope exceeds 256 KiB")
            envelope=json_loads(raw)
        except urllib.error.HTTPError as error:
            data=error.read(MAX_RESPONSE_BYTES+1)
            raw=dict(http_status=error.code,body=data[:MAX_RESPONSE_BYTES].decode(errors='replace'),truncated=len(data)>MAX_RESPONSE_BYTES)
            raise ProviderError('Local model HTTP request failed: '+str(error.code),raw) from error
        except ProviderError:raise
        except Exception as error:raise ProviderError(f"Local model request failed: {type(error).__name__}") from error
        if not isinstance(envelope,dict) or not envelope.get("done") or envelope.get("done_reason")=="length":
            raise ProviderError("Model output incomplete or token budget exhausted",envelope)
        text=envelope.get("response")
        if not isinstance(text,str):raise ProviderError("Model envelope has no response text",envelope)
        return {"text":text,"output_mode":mode,"raw_envelope":envelope,"model":envelope.get("model",model),
                "latency_ms":round((time.monotonic()-started)*1000,2),"input_tokens":envelope.get("prompt_eval_count"),
                "output_tokens":envelope.get("eval_count"),"settings":dict(self.settings),"profile":self.profile,"endpoint":ENDPOINT+"/api/generate"}


class ExpectationOllamaProvider(OllamaProvider):
    """Dedicated V8.1 profile; native model reasoning, no calculator/tools.
    Final JSON and worksheets are retained; internal deliberation is omitted.
    Existing legacy/advanced profiles retain their original behavior.
    """
    def __init__(self,reasoning=False):
        super().__init__('advanced')
        self.settings=dict(temperature=0,seed=7,num_predict=10000 if reasoning else 6000,num_ctx=24576 if reasoning else 16384)
        self.timeout=420 if reasoning else 240
        self.reasoning_enabled=reasoning
        self.profile='expectations-v81-reasoning' if reasoning else 'expectations-v81-direct'
    @staticmethod
    def final_envelope(envelope):
        if not isinstance(envelope,dict):return envelope
        data=dict(envelope)
        if 'thinking' in data:data['internal_deliberation_characters']=len(data.pop('thinking') or '')
        return data
    def generate(self,model,prompt,schema):
        try:result=super().generate(model,prompt,schema)
        except ProviderError as error:
            error.raw_response=self.final_envelope(error.raw_response)
            raise
        result['raw_envelope']=self.final_envelope(result['raw_envelope'])
        result['reasoning_requested']=model=='qwen3.5:27b' and self.reasoning_enabled
        result['internal_deliberation_retained']=False
        return result


class CompactExpectationProvider(ExpectationOllamaProvider):
    """Bounded compact output; legacy V8.1 settings remain unchanged."""
    def __init__(self):
        super().__init__(False)
        self.settings=dict(temperature=0,seed=7,num_predict=2600,num_ctx=12288)
        self.timeout=150
        self.profile='compact-expectations-v82-direct'
