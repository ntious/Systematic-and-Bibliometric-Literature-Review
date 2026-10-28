"""Ollama adapter for explicitly selected installed models on this computer."""
from hashlib import sha256
import ipaddress
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from .evidence import now, text
from .evidence_ai import ModelError
from .reporting import write_json
from .search import _NoRedirect


def endpoint(value):
    parts = urlsplit(value)
    try:
        local = parts.hostname == 'localhost' or ipaddress.ip_address(parts.hostname).is_loopback
    except (ValueError, TypeError):
        local = False
    if parts.scheme != 'http' or not local or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ('', '/'):
        raise ValueError('Ollama endpoint must be a loopback HTTP origin without credentials or path')
    if not parts.port:
        raise ValueError('Ollama endpoint requires an explicit port')
    return value.rstrip('/')


def local_json(url, body=None, timeout=10):
    request = Request(url, data=None if body is None else json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'}, method='GET' if body is None else 'POST')
    try:
        # Never route local questions through an environment-configured proxy or redirect.
        with build_opener(ProxyHandler({}), _NoRedirect).open(request, timeout=timeout) as handle:
            return json.load(handle)
    except HTTPError as exc:
        raise ModelError(f'Local model request failed (HTTP {exc.code})') from None
    except (URLError, TimeoutError, OSError):
        raise ModelError('Local Ollama service unavailable; no cloud fallback or automatic retry') from None
    except (ValueError, UnicodeError):
        raise ModelError('Local model returned invalid JSON') from None


def installed_model(base, model):
    base = endpoint(base)
    model = text(model, 'Model identifier')
    data = local_json(base+'/api/tags')
    matches = [m for m in data.get('models', []) if m.get('name') == model or m.get('model') == model]
    if len(matches) != 1:
        raise ValueError('Select an exact installed Ollama model tag; no models are downloaded automatically')
    found = matches[0]
    info = local_json(base+'/api/show', {'model': model})
    if 'cloud' in model.lower() or any(d.get('remote_host') or d.get('remote_model') for d in (found, info)):
        raise ValueError('Cloud-backed Ollama models are not permitted on the local route')
    if not found.get('digest'):
        raise ValueError('Installed model digest is required for provenance')
    return found


def run_packet(packet, model, output, *, max_output_tokens=2048, base_url='http://127.0.0.1:11434', context_window=4096):
    base = endpoint(base_url)
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 100000:
        raise ValueError('max_output_tokens must be 1–100000')
    if context_window not in (4096,8192):raise ValueError('Unsupported local context size')
    metadata = installed_model(base, model)
    folder = Path(output); folder.mkdir(parents=True, exist_ok=False)
    content = packet['packet']
    body = {'model': model, 'stream': False, 'messages': [
        {'role': 'system', 'content': content['instructions']},
        {'role': 'user', 'content': json.dumps({k:v for k,v in content.items() if k not in ('instructions','response_schema')},ensure_ascii=False)}],
        'format': content['response_schema'], 'tools': [], 'options': {'num_predict': max_output_tokens, 'num_ctx': context_window}}
    manifest = dict(status='running', provider='ollama', requested_model=model, model_digest=metadata['digest'],
                    request_sha256=packet['request_sha256'], started_utc=now(), endpoint=base)
    write_json(folder/'request.json', packet);write_json(folder/'provider-request.json', body)
    write_json(folder/'manifest.json', manifest)
    try:
        response = local_json(base+'/api/chat', body, timeout=90)
        write_json(folder/'raw-response.json', response)
        if response.get('done') is not True or response.get('done_reason') != 'stop':
            raise ModelError('Local model output incomplete; no proposals accepted')
        result = json.loads(response['message']['content'])
        if 'questions' in content:
            from .knowledge_ai import validate_output
            validate_output(result)
        elif not isinstance(result,dict) or set(result)!={'items'} or not isinstance(result['items'],list):
            raise ModelError('Local model response does not match the saved request')
        envelope = dict(provider='ollama', model=response.get('model') or model, requested_model=model,
                        model_digest=metadata['digest'], generated_utc=now(), request_id=packet['request_id'],
                        request_sha256=packet['request_sha256'], endpoint=base, output=result,
                        usage={k:response.get(k) for k in ('prompt_eval_count','eval_count','total_duration')})
        write_json(folder/'response.json',envelope)
        manifest.update(status='complete', finished_utc=now())
        manifest['files']={p.name:sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.name!='manifest.json'}
        write_json(folder/'manifest.json',manifest)
        return envelope
    except Exception:
        manifest.update(status='failed',finished_utc=now());write_json(folder/'manifest.json',manifest)
        raise
