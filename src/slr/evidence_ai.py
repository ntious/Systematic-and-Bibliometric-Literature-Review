"""Optional OpenAI Responses adapter; no model call occurs without run-ai."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

from . import __version__
from .evidence import get_request, now, text
from .reporting import write_json
from .search import urlopen


class ModelError(ValueError):
    pass


def run_openai(database, request_id, model, output, *, max_output_tokens=4096):
    model = text(model, 'Model identifier')
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 100000:
        raise ValueError('max_output_tokens must be 1–100000')
    packet = get_request(database, request_id)
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise ValueError('Set OPENAI_API_KEY in the environment before running a model')
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    write_json(folder / 'request.json', packet)
    manifest = {'status': 'running', 'version': __version__, 'provider': 'openai', 'requested_model': model,
                'request_id': request_id, 'request_sha256': packet['request_sha256'], 'started_utc': now()}
    write_json(folder / 'manifest.json', manifest)
    content = packet['packet']
    body = {'model': model, 'instructions': content['instructions'],
            'input': json.dumps({k: v for k, v in content.items() if k not in ('instructions', 'response_schema')}, ensure_ascii=False),
            'text': {'format': {'type': 'json_schema', 'name': 'evidence_proposals', 'strict': True, 'schema': content['response_schema']}},
            'max_output_tokens': max_output_tokens, 'store': False, 'tools': []}
    write_json(folder / 'provider-request.json', body)
    request = Request('https://api.openai.com/v1/responses', data=json.dumps(body).encode(),
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'User-Agent': 'slr-workbench/' + __version__}, method='POST')
    try:
        # No automatic retry: a timed-out generation may still incur usage.
        try:
            with urlopen(request, timeout=90) as handle:
                response = json.load(handle)
        except HTTPError as exc:
            raise ModelError(f'Model request failed (HTTP {exc.code})') from None
        except (URLError, TimeoutError, OSError):
            raise ModelError('Model connection failed; inspect provider usage before retrying') from None
        except (ValueError, UnicodeError):
            raise ModelError('Model returned invalid JSON') from None
        write_json(folder / 'raw-response.json', response)
        if not isinstance(response, dict) or response.get('status') != 'completed':
            raise ModelError('Model response was incomplete or failed; no proposals were imported')
        chunks = []
        try:
            for item in response.get('output', []):
                if item.get('type') != 'message':
                    continue
                for part in item.get('content', []):
                    if part.get('type') == 'refusal':
                        raise ModelError('Model refused the request; no proposals were imported')
                    if part.get('type') == 'output_text':
                        chunks.append(part['text'])
            result = json.loads(''.join(chunks))
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            if isinstance(exc, ModelError):
                raise
            raise ModelError('Model output did not contain a valid JSON evidence object') from None
        if not isinstance(result, dict) or set(result) != {'items'} or not isinstance(result['items'], list):
            raise ModelError('Model output does not match the expected response object')
        envelope = {'provider': 'openai', 'model': response.get('model') or model, 'requested_model': model,
                    'generated_utc': now(), 'request_id': request_id, 'request_sha256': packet['request_sha256'],
                    'response_id': response.get('id'), 'usage': response.get('usage'), 'output': result}
        write_json(folder / 'response.json', envelope)
        manifest.update(status='complete', finished_utc=now(), response_id=response.get('id'), model=envelope['model'])
        from hashlib import sha256
        manifest['files'] = {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.name != 'manifest.json'}
        write_json(folder / 'manifest.json', manifest)
        return envelope
    except Exception:
        manifest.update(status='failed', finished_utc=now())
        write_json(folder / 'manifest.json', manifest)
        raise
