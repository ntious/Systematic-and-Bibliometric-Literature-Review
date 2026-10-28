"""Guided AI configuration, resource-aware local installation and connection checks."""
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import tarfile
from threading import RLock, Event
import time
from urllib.request import Request, urlopen, build_opener, ProxyHandler
from uuid import uuid4
import zipfile

from . import ai_providers, local_ai
from .evidence import now
from .knowledge_ai import prepare, validate_output

GIB=1024**3
LOCAL_MODELS=[
 {'id':'llama3.2:3b','label':'Llama 3.2 · 3B','download_gb':2.0,'ram_gb':8,'license':'https://ollama.com/library/llama3.2:3b','tier':'Balanced'},
 {'id':'llama3.2:1b','label':'Llama 3.2 · 1B','download_gb':1.3,'ram_gb':4,'license':'https://ollama.com/library/llama3.2:1b','tier':'Lightweight'},
 {'id':'qwen2.5:3b','label':'Qwen 2.5 · 3B','download_gb':1.9,'ram_gb':8,'license':'https://ollama.com/library/qwen2.5:3b','tier':'Balanced'},
 {'id':'gemma3:1b','label':'Gemma 3 · 1B','download_gb':0.8,'ram_gb':4,'license':'https://ollama.com/library/gemma3:1b','tier':'Lightweight'},
 {'id':'llama3.1:8b','label':'Llama 3.1 · 8B','download_gb':4.9,'ram_gb':16,'license':'https://ollama.com/library/llama3.1:8b','tier':'Larger'},
]


def resources(root):
    total=available=None
    system=platform.system()
    if system=='Linux':
        try:
            values={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
            total,available=values['MemTotal'],values['MemAvailable']
            cap=Path('/sys/fs/cgroup/memory.max');used=Path('/sys/fs/cgroup/memory.current')
            if cap.exists() and cap.read_text().strip().isdigit():
                limit=int(cap.read_text());total=min(total,limit);available=min(available,max(0,limit-int(used.read_text())))
        except (OSError,ValueError,KeyError):pass
    elif system=='Windows':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
        mem=Memory();mem.length=ctypes.sizeof(mem)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):total,available=mem.total,mem.available
    elif system=='Darwin':
        try:
            total=int(subprocess.check_output(['sysctl','-n','hw.memsize'],timeout=5))
            import re
            vm=subprocess.check_output(['vm_stat'],timeout=5,text=True)
            page=int(re.search(r'page size of (\d+)',vm).group(1))
            available=sum(int(v) for v in re.findall(r'Pages (?:free|inactive|speculative):\s+(\d+)',vm))*page
        except (OSError,ValueError,subprocess.SubprocessError,AttributeError):pass
    cpus=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else (os.cpu_count() or 1)
    return dict(os=system,architecture=platform.machine(),cpu_threads=cpus,ram_total_gb=round(total/GIB,1) if total else None,
                ram_available_gb=round(available/GIB,1) if available is not None else None,
                disk_free_gb=round(shutil.disk_usage(root).free/GIB,1),gpu='Not measured; recommendations use CPU and system RAM',
                note='Conservative estimates, not a performance guarantee. Memory is checked again before downloading. CPU generation may be slow.')


def recommendations(info):
    rows=[]
    for m in LOCAL_MODELS:
        reasons=[]
        if info['ram_available_gb'] is None:reasons.append('Available memory could not be measured')
        elif info['ram_available_gb']<m['ram_gb']:reasons.append(f"Needs about {m['ram_gb']} GB available RAM")
        disk=12+2*m['download_gb']
        if info['disk_free_gb']<disk:reasons.append(f'Needs about {disk:g} GB free including runtime, download and headroom')
        if info['cpu_threads']<2:reasons.append('At least two CPU threads recommended')
        rows.append(dict(m,eligible=not reasons,reasons=reasons,estimated_free_disk_gb=disk,recommended=False))
    good=[m for m in rows if m['eligible']]
    if good:
        # Prefer a modest 3B model even on a large machine; avoid consuming all resources.
        next((m for m in good if m['id']=='llama3.2:3b'),good[0])['recommended']=True
    return rows


def _atomic(path,data):
    temp=path.with_suffix('.tmp')
    with open(temp,'w',encoding='utf-8') as handle:
        if os.name!='nt':os.chmod(temp,0o600)
        json.dump(data,handle,ensure_ascii=False,indent=2)
    temp.replace(path)


class AISettings:
    def __init__(self,workspace,executor):
        self.root=Path(workspace)/'.litatlas-ai';self.root.mkdir(parents=True,exist_ok=True)
        if os.name!='nt':os.chmod(self.root,0o700)
        self.executor=executor;self.lock=RLock();self.keys={};self.process=None;self.cancel=Event()
        self.path=self.root/'settings.json';self.state_path=self.root/'setup.json'
        self.config=json.loads(self.path.read_text()) if self.path.exists() else {'mode':'off'}
        self.state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {'status':'idle'}
        if self.state.get('status')=='running':self.progress(status='failed',stage='Setup interrupted by restart. Click download again to retry.')
        # Dedicated managed endpoint: never attach to an unrelated model server.
        self.base='http://127.0.0.1:11435'

    def progress(self,**values):
        with self.lock:
            previous=(self.state.get('status'),self.state.get('stage'))
            self.state.update(values,updated_utc=now());_atomic(self.state_path,self.state)
            if previous!=(self.state.get('status'),self.state.get('stage')):
                with open(self.root/'SETUP_LOG.md','a',encoding='utf-8') as log:
                    log.write('\n## '+self.state['updated_utc']+' — '+self.state.get('status','')+'\n\n'+self.state.get('stage','')+'\n')

    def key(self,provider):
        if provider in self.keys:return self.keys[provider]
        try:
            import keyring
            return keyring.get_password('LitAtlas:'+str(self.root.resolve()),provider)
        except Exception:return None

    def status(self):
        info=resources(self.root)
        config=dict(self.config)
        config['key_configured']=bool(self.key(config.get('provider',''))) if config.get('mode')=='cloud' else False
        return {'config':config,'setup':dict(self.state),'resources':info,'local_models':recommendations(info),
                'providers':[{'id':k,**v} for k,v in ai_providers.PROVIDERS.items()],
                'platform_supported':platform.system() in ('Linux','Windows','Darwin') and platform.machine().lower() in ('x86_64','amd64','arm64','aarch64')}

    def cloud_models(self,provider,key,remember=False):
        rows=ai_providers.models(provider,key)
        if not rows:raise ValueError('No supported text-generation models available for this key')
        self.keys[provider]=key
        storage='session';warning=None
        if remember:
            try:
                import keyring
                # Fail rather than using an insecure fallback backend.
                backend=keyring.get_keyring();name=type(backend).__module__
                if not name.startswith(('keyring.backends.Windows','keyring.backends.macOS','keyring.backends.SecretService','keyring.backends.kwallet')):
                    raise ValueError('No supported operating-system credential store')
                keyring.set_password('LitAtlas:'+str(self.root.resolve()),provider,key);storage='system'
            except Exception:warning='Secure credential storage is unavailable. Key is kept for this session only.'
        return {'models':rows,'key_storage':storage,'warning':warning}

    def save_cloud(self,provider,model):
        if self.state.get('status')=='running':raise ValueError('Wait for local setup to finish or turn AI off to cancel it')
        key=self.key(provider)
        if model not in {m['id'] for m in ai_providers.models(provider,key)}:raise ValueError('Choose an available model from the connection check')
        self.config={'mode':'cloud','provider':provider,'model':model,'updated_utc':now()};_atomic(self.path,self.config)
        return self.status()

    def disable(self):
        self.cancel.set()
        self.config={'mode':'off','updated_utc':now()};_atomic(self.path,self.config);return self.status()

    def remove_key(self,provider):
        if provider not in ai_providers.PROVIDERS:raise ValueError('Unknown provider')
        self.keys.pop(provider,None)
        warning=None
        try:
            import keyring
            service='LitAtlas:'+str(self.root.resolve())
            if keyring.get_password(service,provider) is not None:keyring.delete_password(service,provider)
        except Exception:
            warning='Session key removed, but secure-store deletion could not be verified. Check your operating-system credential manager.'
        if self.config.get('provider')==provider:self.disable()
        return {**self.status(),'credential_warning':warning}

    def setup(self,model):
        with self.lock:
            if self.state.get('status')=='running':raise ValueError('A local setup is already running')
            choices=recommendations(resources(self.root));choice=next((m for m in choices if m['id']==model),None)
            if not choice or not choice['eligible']:raise ValueError('Selected model does not fit the current resource estimate. Refresh the device check.')
            self.cancel.clear()
            self.state={'status':'running','stage':'Preparing local AI','model':model,'percent':0,'started_utc':now(),'license':choice['license'],'license_accepted_utc':now()};self.progress()
            self.executor.submit(self._setup,model)
        return self.status()

    def _asset(self):
        system,arch=platform.system(),platform.machine().lower()
        architecture='arm64' if arch in ('arm64','aarch64') else 'amd64' if arch in ('amd64','x86_64') else None
        if not architecture:raise ValueError('Automatic runtime setup is not supported on this processor')
        name={'Linux':f'ollama-linux-{architecture}.tar.zst','Windows':f'ollama-windows-{architecture}.zip','Darwin':'ollama-darwin.tgz'}.get(system)
        if not name:raise ValueError('Automatic runtime setup is not supported on this operating system')
        with urlopen(Request('https://api.github.com/repos/ollama/ollama/releases/latest',headers={'User-Agent':'LitAtlas'}),timeout=30) as handle:release=json.load(handle)
        asset=next((a for a in release['assets'] if a['name']==name),None)
        if not asset or not str(asset.get('digest','')).startswith('sha256:'):raise ValueError('Official runtime archive with SHA-256 verification is unavailable')
        url=asset['browser_download_url']
        if not url.startswith('https://github.com/ollama/ollama/releases/download/'):raise ValueError('Unexpected runtime download source')
        return release['tag_name'],asset

    def restore_library_links(self,destination):
        # Repair version aliases for managed archives extracted by earlier builds.
        if os.name=='nt':return
        for source in destination.rglob('*.so.*'):
            match=re.fullmatch(r'(.+\.so)\.(\d+)\.\d+\.\d+',source.name)
            if not match or not source.is_file():continue
            for name in (match[1],match[1]+'.'+match[2]):
                target=source.with_name(name)
                if not target.exists() and not target.is_symlink():target.symlink_to(source.name)


    def install_runtime(self):
        manifest=self.root/'runtime.json'
        if manifest.exists():
            data=json.loads(manifest.read_text());binary=Path(data['binary'])
            if binary.is_file() and sha256(binary.read_bytes()).hexdigest()==data['binary_sha256']:
                self.restore_library_links(self.root/'runtime')
                return binary
            raise ValueError('Managed runtime changed or is missing; inspect the installation before retrying')
        version,asset=self._asset();archive=self.root/(asset['name']+'.part')
        self.progress(stage='Downloading the local AI engine',percent=0,downloaded_bytes=0,total_bytes=asset['size'])
        digest=sha256();completed=0;last=0
        with urlopen(asset['browser_download_url'],timeout=60) as response, open(archive,'wb') as output:
            while True:
                if self.cancel.is_set():raise ValueError('Setup cancelled. AI remains off.')
                chunk=response.read(1024*1024)
                if not chunk:break
                completed+=len(chunk);digest.update(chunk);output.write(chunk)
                if time.monotonic()-last>0.5:
                    self.progress(percent=round(100*completed/asset['size'],1),downloaded_bytes=completed);last=time.monotonic()
        if completed!=asset['size'] or digest.hexdigest()!=asset['digest'].split(':',1)[1]:
            archive.unlink(missing_ok=True);raise ValueError('Runtime download verification failed. No executable was installed.')
        self.progress(stage='Installing local runtime',percent=0)
        destination=self.root/'runtime';destination.mkdir(exist_ok=True)
        def safe(name):
            name=name.replace('\\','/');path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or ':' in name:raise ValueError('Unsafe archive path')
            return destination.joinpath(*path.parts)
        links=[]
        if asset['name'].endswith('.zip'):
            with zipfile.ZipFile(archive) as package:
                for member in package.infolist():
                    target=safe(member.filename)
                    if member.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with package.open(member) as source,open(target,'wb') as output:shutil.copyfileobj(source,output)
        else:
            import zstandard
            with open(archive,'rb') as stream:
                decoder=zstandard.ZstdDecompressor().stream_reader(stream) if asset['name'].endswith('.zst') else stream
                with tarfile.open(fileobj=decoder,mode='r|' if asset['name'].endswith('.zst') else 'r|gz') as package:
                    for member in package:
                        target=safe(member.name)
                        if member.isdir():target.mkdir(parents=True,exist_ok=True)
                        elif member.isfile():
                            target.parent.mkdir(parents=True,exist_ok=True)
                            with package.extractfile(member) as source,open(target,'wb') as output:shutil.copyfileobj(source,output)
                            if os.name!='nt':target.chmod(member.mode & 0o755)
                        elif member.issym() or member.islnk():
                            link=(target.parent/member.linkname).resolve() if member.issym() else safe(member.linkname).resolve()
                            if not link.is_relative_to(destination.resolve()):raise ValueError('Unsafe archive link')
                            links.append((target,link,member.issym()))
        for target,source,is_symbolic in links:
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() or target.is_symlink():continue
            if is_symbolic:target.symlink_to(os.path.relpath(source,target.parent))
            else:os.link(source,target)
        self.restore_library_links(destination)
        archive.unlink(missing_ok=True)
        names=['ollama.exe'] if os.name=='nt' else ['ollama']
        candidates=[p for p in destination.rglob('*') if p.is_file() and p.name in names]
        if len(candidates)!=1:raise ValueError('Runtime executable not found after extraction')
        binary=candidates[0]
        _atomic(manifest,dict(version=version,source=asset['browser_download_url'],archive_sha256=digest.hexdigest(),binary=str(binary.resolve()),binary_sha256=sha256(binary.read_bytes()).hexdigest()))
        return binary

    def start_runtime(self,binary):
        if self.process and self.process.poll() is None:return
        env=dict(os.environ,OLLAMA_HOST='127.0.0.1:11435',OLLAMA_MODELS=str((self.root/'models').resolve()),OLLAMA_NO_CLOUD='1',OLLAMA_CONTEXT_LENGTH='4096',OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1')
        log=open(self.root/'runtime.log','ab')
        self.process=subprocess.Popen([str(binary),'serve'],env=env,stdout=log,stderr=log,stdin=subprocess.DEVNULL)
        log.close()
        for _ in range(100):
            if self.process.poll() is not None:raise ValueError('Local runtime did not start. Check the setup log.')
            try:local_ai.local_json(self.base+'/api/tags',timeout=1);return
            except ValueError:time.sleep(0.2)
        raise ValueError('Local runtime did not become ready. Retry setup.')

    def pull(self,model):
        request=Request(self.base+'/api/pull',data=json.dumps({'model':model,'stream':True}).encode(),headers={'Content-Type':'application/json'})
        self.progress(stage='Downloading '+model,percent=0,downloaded_bytes=0,total_bytes=0)
        success=False;last=0
        with build_opener(ProxyHandler({}),local_ai._NoRedirect).open(request,timeout=90) as response:
            for line in response:
                if self.cancel.is_set():raise ValueError('Setup cancelled. AI remains off.')
                data=json.loads(line)
                if data.get('error'):raise ValueError('Model download failed. Check internet access and retry setup.')
                if data.get('status')=='success':success=True
                if time.monotonic()-last>0.5 or success:
                    total=data.get('total',0);completed=data.get('completed',0)
                    status=str(data.get('status',''))
                    stage=('Model download complete' if success else 'Verifying model download' if 'verifying' in status else 'Finishing model setup' if 'writing' in status else 'Finding model files' if 'manifest' in status else 'Downloading model files')
                    self.progress(stage=stage,download_status=status,percent=round(100*completed/total,1) if total else 0,downloaded_bytes=completed,total_bytes=total);last=time.monotonic()
        if not success:raise ValueError('Model download interrupted. Click download again to resume.')

    def _setup(self,model):
        try:
            binary=self.install_runtime()
            if self.cancel.is_set():raise ValueError('Setup cancelled. AI remains off.')
            self.start_runtime(binary);self.pull(model)
            self.progress(stage='Testing local model with a sample question',percent=100)
            metadata=local_ai.installed_model(self.base,model)
            result=self._test('ollama',model)
            with self.lock:
                if self.cancel.is_set():raise ValueError('Setup cancelled. AI remains off.')
                self.config={'mode':'local','provider':'ollama','model':model,'base_url':self.base,'model_digest':metadata['digest'],'updated_utc':now()};_atomic(self.path,self.config)
            self.progress(status='complete',stage='Local AI is ready',percent=100,test_proposals=len(result['output']['items']))
        except Exception as exc:
            # Avoid leaking arbitrary transport/provider payloads into status messages.
            message=str(exc) if isinstance(exc,ValueError) else 'Setup failed. Check internet access, free space and the local setup log; retry when ready.'
            self.progress(status='failed',stage=message,percent=0)

    def run_packet(self,packet,folder,*,allow_external=False,config=None):
        selected=dict(config or self.config)
        if selected.get('mode')=='off':raise ValueError('Open Settings and select an AI model first')
        if selected.get('mode')=='local':
            # A conservative byte upper bound avoids silently truncating source packets.
            content=packet['packet']
            encoded=json.dumps(content,ensure_ascii=False).encode('utf-8')
            if len(encoded)+1024+256>8192:
                raise ValueError('This source packet is too large for the local model. Use shorter source sections or a cloud model; automatic full-paper chunking is not implemented yet.')
            self.start_runtime(self.install_runtime())
            return local_ai.run_packet(packet,selected['model'],folder,base_url=self.base,max_output_tokens=1024,context_window=8192)
        if not allow_external:raise ValueError('Confirm sending this saved request to the selected cloud provider')
        return ai_providers.run_packet(packet,selected['model'],folder,provider=selected['provider'],key=self.key(selected['provider']),max_output_tokens=4096)


    def _test(self,provider,model):
        packet=prepare([dict(case_id='connection-test',question='Which methods are used to summarise the characteristics of included studies?',cohort='setup',discipline='general',anchors=[{'quote':'Synthetic connection test'}])])['packets'][0]
        folder=self.root/'checks'/uuid4().hex
        if provider=='ollama':return local_ai.run_packet(packet,model,folder,base_url=self.base,max_output_tokens=1024)
        return ai_providers.run_packet(packet,model,folder,provider=provider,key=self.key(provider),max_output_tokens=1024)

    def test(self):
        if self.config.get('mode')=='off':raise ValueError('Select and configure an AI model first')
        if self.config['provider']=='ollama':self.start_runtime(self.install_runtime())
        response=self._test(self.config['provider'],self.config['model'])
        return {'connected':True,'provider':response['provider'],'model':response['model'],'proposal_count':len(response['output']['items']),'notice':'Connection test only. Suggestions remain unapproved.'}

    def close(self):
        self.cancel.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
