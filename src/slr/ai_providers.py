"""Fixed-host cloud providers. Credentials never enter persisted request packets."""
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .evidence import now
from .evidence_ai import ModelError
from .reporting import write_json
from .search import urlopen

PROVIDERS = {
 'openai': {'label':'OpenAI / GPT', 'models':'https://api.openai.com/v1/models', 'keys':'https://platform.openai.com/api-keys'},
 'anthropic': {'label':'Anthropic / Claude', 'models':'https://api.anthropic.com/v1/models', 'keys':'https://console.anthropic.com/settings/keys'},
 'google': {'label':'Google / Gemini', 'models':'https://generativelanguage.googleapis.com/v1beta/models', 'keys':'https://aistudio.google.com/apikey'},
 'mistral': {'label':'Mistral AI', 'models':'https://api.mistral.ai/v1/models', 'keys':'https://console.mistral.ai/api-keys/'},
 'deepseek': {'label':'DeepSeek', 'models':'https://api.deepseek.com/models', 'keys':'https://platform.deepseek.com/api_keys'},
}


def call(provider, key, url, body=None):
    if provider not in PROVIDERS or not isinstance(key,str) or not key.strip() or len(key)>4096:
        raise ValueError('Select a provider and enter a valid API key')
    key=key.strip()
    if any(ord(c)<32 or ord(c)==127 for c in key):raise ValueError('API key contains invalid characters')
    headers={'Content-Type':'application/json'}
    if provider=='anthropic':headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
    elif provider=='google':headers['x-goog-api-key']=key
    else:headers['Authorization']='Bearer '+key
    request=Request(url,data=None if body is None else json.dumps(body).encode(),headers=headers,method='GET' if body is None else 'POST')
    try:
        with urlopen(request,timeout=90) as handle:return json.load(handle)
    except HTTPError as exc:
        raise ModelError(f'Provider request failed (HTTP {exc.code}). Check API access, billing and model availability.') from None
    except (URLError,TimeoutError,OSError):
        raise ModelError('Provider connection failed. Inspect usage before retrying; no automatic retry.') from None
    except (ValueError,UnicodeError):raise ModelError('Provider returned invalid JSON') from None


def models(provider,key):
    if provider not in PROVIDERS:raise ValueError('Choose one of the five supported cloud providers')
    data=call(provider,key,PROVIDERS[provider]['models'])
    rows=[]
    for item in data.get('models',[]) if provider=='google' else data.get('data',[]):
        name=item.get('name','').removeprefix('models/') if provider=='google' else item.get('id','')
        if not re.fullmatch(r'[A-Za-z0-9._:/-]{1,160}',name):continue
        if provider=='google' and 'generateContent' not in item.get('supportedGenerationMethods',[]):continue
        if provider=='openai' and (not name.startswith(('gpt-','o1','o3','o4')) or any(x in name for x in ('audio','realtime','image','transcribe','search','codex','tts'))):continue
        if provider=='mistral' and item.get('capabilities',{}).get('completion_chat') is False:continue
        rows.append({'id':name,'label':item.get('displayName') or item.get('display_name') or name})
    return sorted({r['id']:r for r in rows}.values(),key=lambda r:r['id'])


def run_packet(packet,model,output,*,provider,key,max_output_tokens=2048):
    if provider=='openai':
        from .evidence_ai import run_packet as run_openai
        return run_openai(packet,model,output,max_output_tokens=max_output_tokens,api_key=key)
    if provider not in PROVIDERS or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,160}',model):raise ValueError('Invalid provider or model')
    if type(max_output_tokens) is not int or not 1<=max_output_tokens<=100000:raise ValueError('Invalid output token limit')
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False)
    content=packet['packet'];instructions=content['instructions']+'\nReturn JSON matching this schema: '+json.dumps(content['response_schema'])
    user=json.dumps({k:v for k,v in content.items() if k not in ('instructions','response_schema')},ensure_ascii=False)
    if provider=='anthropic':
        url='https://api.anthropic.com/v1/messages';body={'model':model,'max_tokens':max_output_tokens,'system':instructions,'messages':[{'role':'user','content':user}]}
    elif provider=='google':
        url='https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent'
        body={'systemInstruction':{'parts':[{'text':instructions}]},'contents':[{'role':'user','parts':[{'text':user}]}], 'generationConfig':{'responseMimeType':'application/json','maxOutputTokens':max_output_tokens}}
    else:
        url=('https://api.mistral.ai/v1' if provider=='mistral' else 'https://api.deepseek.com')+'/chat/completions'
        body={'model':model,'max_tokens':max_output_tokens,'messages':[{'role':'system','content':instructions},{'role':'user','content':user}], 'response_format':{'type':'json_object'},'stream':False}
    manifest=dict(status='running',provider=provider,requested_model=model,request_sha256=packet['request_sha256'],started_utc=now())
    write_json(folder/'request.json',packet);write_json(folder/'provider-request.json',body);write_json(folder/'manifest.json',manifest)
    try:
        response=call(provider,key,url,body);write_json(folder/'raw-response.json',response)
        if provider=='anthropic':
            if response.get('stop_reason')!='end_turn':raise ModelError('Provider response incomplete or refused')
            result=json.loads(''.join(p['text'] for p in response.get('content',[]) if p.get('type')=='text'))
        elif provider=='google':
            candidate=response['candidates'][0]
            if candidate.get('finishReason')!='STOP':raise ModelError('Provider response incomplete or blocked')
            result=json.loads(''.join(p.get('text','') for p in candidate['content']['parts']))
        else:
            choice=response['choices'][0]
            if choice.get('finish_reason')!='stop':raise ModelError('Provider response incomplete or refused')
            result=json.loads(choice['message']['content'])
        if 'questions' in content:
            from .knowledge_ai import validate_output
            validate_output(result)
        elif not isinstance(result,dict) or set(result)!={'items'} or not isinstance(result['items'],list):
            raise ModelError('Provider output does not match the saved request')
        envelope=dict(provider=provider,model=response.get('model') or response.get('modelVersion') or model,requested_model=model,
                      request_id=packet['request_id'],request_sha256=packet['request_sha256'],generated_utc=now(),
                      response_id=response.get('id') or response.get('responseId'),usage=response.get('usage') or response.get('usageMetadata'),output=result)
        write_json(folder/'response.json',envelope)
        manifest.update(status='complete',finished_utc=now())
        manifest['files']={p.name:sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.name!='manifest.json'}
        write_json(folder/'manifest.json',manifest);return envelope
    except Exception:
        manifest.update(status='failed',finished_utc=now());write_json(folder/'manifest.json',manifest);raise
