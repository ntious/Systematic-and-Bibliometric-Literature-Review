from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import io
import json
import tarfile
from pathlib import Path

import pytest

from slr import ai_setup, ai_providers


def info(ram=10,disk=50,cpu=4):
    return {'ram_available_gb':ram,'disk_free_gb':disk,'cpu_threads':cpu}


def test_resource_filter_recommends_balanced_model_without_using_all_memory():
    rows=ai_setup.recommendations(info())
    assert next(m for m in rows if m['recommended'])['id']=='llama3.2:3b'
    assert not next(m for m in rows if m['id']=='llama3.1:8b')['eligible']
    light=ai_setup.recommendations(info(ram=5))
    assert {m['id'] for m in light if m['eligible']}=={'llama3.2:1b','gemma3:1b'}


@pytest.mark.parametrize('data',[info(ram=None),info(ram=2),info(disk=2),info(cpu=1)])
def test_insufficient_or_unknown_resources_offer_no_download(data):
    assert not any(m['eligible'] for m in ai_setup.recommendations(data))


@pytest.fixture
def settings(tmp_path):
    with ThreadPoolExecutor(max_workers=1) as executor:
        value=ai_setup.AISettings(tmp_path,executor)
        yield value
        value.close()


def test_server_rechecks_resources_before_starting_download(settings,monkeypatch):
    monkeypatch.setattr(ai_setup,'resources',lambda root:info(ram=2))
    with pytest.raises(ValueError,match='does not fit'):settings.setup('llama3.2:3b')
    with pytest.raises(ValueError):settings.setup('unknown:999b')
    assert settings.state['status']=='idle'


def test_api_key_never_saved_or_returned(settings,monkeypatch):
    monkeypatch.setattr(ai_providers,'models',lambda provider,key:[{'id':'test-model','label':'Test'}])
    monkeypatch.setattr(ai_setup,'resources',lambda root:{**info(), 'os':'Linux','architecture':'x86_64'})
    result=settings.cloud_models('openai','SECRET-TEST-KEY')
    assert result['key_storage']=='session'
    settings.save_cloud('openai','test-model')
    assert 'SECRET' not in json.dumps(settings.status())
    for p in settings.root.rglob('*'):
        if p.is_file():assert 'SECRET' not in p.read_text()
    assert settings.key('openai')=='SECRET-TEST-KEY'
    with pytest.raises(ValueError):settings.save_cloud('openai','not-in-list')
    settings.remove_key('openai')
    assert settings.config['mode']=='off'


def test_failed_secure_store_is_explicit_session_fallback(settings,monkeypatch):
    import keyring
    monkeypatch.setattr(ai_providers,'models',lambda *args:[{'id':'test','label':'Test'}])
    monkeypatch.setattr(keyring,'get_keyring',lambda:object())
    result=settings.cloud_models('google','SECRET',remember=True)
    assert result['key_storage']=='session' and result['warning']


def test_interrupted_setup_is_reported(tmp_path):
    folder=tmp_path/'.litatlas-ai';folder.mkdir();(folder/'setup.json').write_text('{"status":"running"}')
    with ThreadPoolExecutor() as executor:
        settings=ai_setup.AISettings(tmp_path,executor)
        assert settings.status()['setup']['status']=='failed'


def test_archive_path_traversal_is_rejected(settings,monkeypatch):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as archive:
        member=tarfile.TarInfo('../escape');member.size=1;archive.addfile(member,io.BytesIO(b'x'))
    raw=stream.getvalue()
    asset=dict(name='ollama-darwin.tgz',browser_download_url='https://github.com/ollama/ollama/releases/download/test/archive',size=len(raw),digest='sha256:'+sha256(raw).hexdigest())
    monkeypatch.setattr(settings,'_asset',lambda:('test',asset))
    class Response(io.BytesIO):
        pass
    monkeypatch.setattr(ai_setup,'urlopen',lambda *a,**k:Response(raw))
    with pytest.raises(ValueError,match='Unsafe archive'):settings.install_runtime()
    assert not (settings.root.parent/'escape').exists()


def test_archive_digest_mismatch_prevents_execution(settings,monkeypatch):
    asset=dict(name='archive.zip',browser_download_url='https://github.com/ollama/ollama/releases/download/test/archive',size=3,digest='sha256:'+'0'*64)
    monkeypatch.setattr(settings,'_asset',lambda:('test',asset))
    monkeypatch.setattr(ai_setup,'urlopen',lambda *a,**k:io.BytesIO(b'bad'))
    with pytest.raises(ValueError,match='verification failed'):settings.install_runtime()
    assert not (settings.root/'runtime.json').exists()


@pytest.mark.parametrize('provider',['anthropic','google','mistral','deepseek'])
def test_cloud_adapters_preserve_question_only_input_without_persisting_key(provider,tmp_path,monkeypatch):
    from slr.knowledge_ai import prepare
    packet=prepare([dict(case_id='X',question='Which methods are used?',cohort='x',discipline='x',anchors=[{'quote':'q'}],paper='PRIVATE.pdf')])['packets'][0]
    captured=[]
    def fake(p,key,url,body):
        captured.append(body)
        if p=='anthropic':return {'stop_reason':'end_turn','content':[{'type':'text','text':'{"items":[]}'}]}
        if p=='google':return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"items":[]}'}]}}]}
        return {'choices':[{'finish_reason':'stop','message':{'content':'{"items":[]}'}}]}
    monkeypatch.setattr(ai_providers,'call',fake)
    result=ai_providers.run_packet(packet,'test-model',tmp_path/'run',provider=provider,key='SECRET-KEY')
    assert result['provider']==provider
    assert 'PRIVATE' not in json.dumps(captured)
    assert 'Which methods are used?' in json.dumps(captured)
    for f in (tmp_path/'run').iterdir():assert 'SECRET-KEY' not in f.read_text()


def test_turning_ai_off_during_setup_cannot_reenable_it(settings,monkeypatch):
    monkeypatch.setattr(settings,'install_runtime',lambda:Path('/fake/runtime'))
    monkeypatch.setattr(settings,'start_runtime',lambda binary:None)
    monkeypatch.setattr(settings,'pull',lambda model:settings.disable())
    monkeypatch.setattr(ai_setup.local_ai,'installed_model',lambda *a:{'digest':'x'})
    monkeypatch.setattr(settings,'_test',lambda *a:{'output':{'items':[]}})
    settings._setup('llama3.2:3b')
    assert settings.config['mode']=='off'
    assert settings.state['status']=='failed' and 'cancelled' in settings.state['stage']


def test_control_characters_in_key_are_rejected_without_echoing_secret():
    with pytest.raises(ValueError) as exc:
        ai_providers.call('openai','SECRET\nKEY',ai_providers.PROVIDERS['openai']['models'])
    assert 'SECRET' not in str(exc.value)


def test_portable_archive_keeps_internal_library_links(settings,monkeypatch):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as archive:
        for name in ('bin/ollama','lib/ollama/libexample.so.0.1.0'):
            member=tarfile.TarInfo(name);member.size=1;member.mode=0o755;archive.addfile(member,io.BytesIO(b'x'))
        link=tarfile.TarInfo('lib/ollama/libexample.so.0');link.type=tarfile.SYMTYPE;link.linkname='libexample.so.0.1.0';archive.addfile(link)
    raw=stream.getvalue();asset=dict(name='ollama-darwin.tgz',browser_download_url='https://github.com/ollama/ollama/releases/download/test/archive',size=len(raw),digest='sha256:'+sha256(raw).hexdigest())
    monkeypatch.setattr(settings,'_asset',lambda:('test',asset));monkeypatch.setattr(ai_setup,'urlopen',lambda *a,**k:io.BytesIO(raw))
    assert settings.install_runtime().name=='ollama'
    link=settings.root/'runtime/lib/ollama/libexample.so.0'
    assert link.is_symlink() and link.read_bytes()==b'x'


def test_archive_link_outside_runtime_is_rejected(settings,monkeypatch):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as archive:
        link=tarfile.TarInfo('link');link.type=tarfile.SYMTYPE;link.linkname='../../outside';archive.addfile(link)
    raw=stream.getvalue();asset=dict(name='ollama-darwin.tgz',browser_download_url='https://github.com/ollama/ollama/releases/download/test/archive',size=len(raw),digest='sha256:'+sha256(raw).hexdigest())
    monkeypatch.setattr(settings,'_asset',lambda:('test',asset));monkeypatch.setattr(ai_setup,'urlopen',lambda *a,**k:io.BytesIO(raw))
    with pytest.raises(ValueError,match='Unsafe archive link'):settings.install_runtime()


def test_local_source_packet_budget_blocks_silent_truncation(settings,monkeypatch,tmp_path):
    settings.config={'mode':'local','provider':'ollama','model':'llama3.2:3b'}
    monkeypatch.setattr(settings,'start_runtime',lambda *a:pytest.fail('Oversized source sent'))
    packet={'request_id':1,'request_sha256':'test','packet':{'instructions':'Review source','response_schema':{},'data':'x'*10000}}
    with pytest.raises(ValueError,match='too large'):settings.run_packet(packet,tmp_path/'result')


def test_local_short_source_uses_bounded_context(settings,monkeypatch,tmp_path):
    settings.config={'mode':'local','provider':'ollama','model':'llama3.2:3b'}
    monkeypatch.setattr(settings,'install_runtime',lambda:Path('/fake'))
    monkeypatch.setattr(settings,'start_runtime',lambda *a:None)
    captured=[]
    monkeypatch.setattr(ai_setup.local_ai,'run_packet',lambda *a,**k:captured.append(k) or {'output':{'items':[]}})
    packet={'request_id':1,'request_sha256':'test','packet':{'instructions':'Review source','response_schema':{},'data':'Short source section'}}
    settings.run_packet(packet,tmp_path/'result')
    assert captured[0]['context_window']==8192 and captured[0]['max_output_tokens']==1024
