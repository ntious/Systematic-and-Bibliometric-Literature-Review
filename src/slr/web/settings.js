'use strict';
let aiSetupTimer=null;
window.renderAISettings=async function(){
  clearTimeout(aiSetupTimer);
  const root=document.querySelector('#main');
  root.innerHTML=heading('AI that fits your research.','Choose where AI runs. You stay in control of every research decision.')+'<div class="card"><div class="card-body">Checking this device…</div></div>';
  try{const data=await api('/api/ai-settings');if(S.page!=='settings')return;drawAISettings(data);}catch(e){root.innerHTML=heading('AI settings','Setup needs attention.')+`<div class="notice orange">${esc(e.message)}</div>`;}
};
function drawAISettings(d){
  const cfg=d.config,job=d.setup,r=d.resources,local=cfg.mode!=='cloud';
  const chosen=d.local_models.find(m=>m.eligible&&m.id===cfg.model)?.id||d.local_models.find(m=>m.recommended)?.id;
  const ready=cfg.mode==='off'?'AI is off':`${cfg.mode==='local'?'Local':'Cloud'} · ${cfg.model}`;
  $('#main').innerHTML=heading('AI that fits your research.','A guided setup for this device. No terminal or configuration files needed.')+`
  <div class="notice">${icon('lock')}<span><strong>${esc(ready)}</strong> · AI suggestions always need researcher review. Cloud use sends your selected input to the provider; local processing stays on this device after setup.</span></div>
  <div class="card"><div class="card-head"><h2>1. Choose where AI runs</h2></div><div class="card-body"><div class="ai-mode-grid">
  <button class="ai-mode ${local?'selected':''}" id="ai-local-mode"><strong>Local · open models</strong><span>Runs on this computer. No API key. Internet is needed for the initial downloads.</span></button>
  <button class="ai-mode ${!local?'selected':''}" id="ai-cloud-mode" ${job.status==='running'?'disabled':''}><strong>Cloud · API providers</strong><span>Choose a provider and connect your account. API billing and data policies apply.</span></button></div>
  <div class="ai-status-actions"><button class="button soft" id="ai-disable">Turn AI off</button><button class="button soft" id="ai-connection-test" ${cfg.mode==='off'?'disabled':''}>Test selected model</button><span id="ai-test-result" role="status"></span></div></div></div>
  <section id="ai-local-panel" ${local?'':'hidden'} class="card"><div class="card-head"><h2>2. Choose a model for this device</h2><button class="button soft small" id="ai-rescan">Check device again</button></div><div class="card-body">
  <div class="ai-device-grid"><div><small>Available memory</small><strong>${r.ram_available_gb===null?'Could not measure':esc(r.ram_available_gb)+' GB'} <small>of ${esc(r.ram_total_gb??'?')} GB</small></strong></div><div><small>Free storage</small><strong>${esc(r.disk_free_gb)} GB</strong></div><div><small>CPU threads</small><strong>${esc(r.cpu_threads)}</strong></div><div><small>Device</small><strong>${esc(r.os)} · ${esc(r.architecture)}</strong></div></div>
  <p class="detail-caption">Models below meet conservative memory and storage estimates, including room for the runtime. This is a fit estimate, not a guarantee of speed or research quality. GPU capacity is not measured.</p>
  ${!d.platform_supported?'<div class="notice orange">Automatic installation is not available for this device architecture.</div>':''}
  <div class="ai-model-grid">${d.local_models.filter(m=>m.eligible).map(m=>`<label class="ai-model"><input type="radio" name="ai-local-model" ${job.status==='running'?'disabled':''} value="${esc(m.id)}" ${chosen===m.id?'checked':''}><span><strong>${esc(m.label)}</strong>${m.recommended?'<span class="pill purple">Recommended fit</span>':''}<small>${esc(m.tier)} · about ${m.download_gb} GB download · ${m.ram_gb} GB available RAM</small><a href="${esc(m.license)}" target="_blank" rel="noopener noreferrer">Model details & license ↗</a></span></label>`).join('')||'<p>No model in the current catalogue fits the available resources. Free memory/storage and check again, or choose a cloud provider.</p>'}</div>
  <details><summary>Models outside the current device estimate</summary>${d.local_models.filter(m=>!m.eligible).map(m=>`<p class="detail-caption">${esc(m.label)} — ${esc(m.reasons.join('; '))}</p>`).join('')||'<p class="detail-caption">All catalogue models fit the current estimate.</p>'}</details>
  <p class="detail-caption">The first setup also downloads the verified Ollama runtime (download size varies by platform). Llama, Gemma and Qwen have different licenses; local/open weights does not always mean an OSI open-source license.</p>
  <label class="ai-consent"><input type="checkbox" id="ai-license"> I have reviewed and accept the selected model’s license and agree to download it on this device.</label>
  <button class="button primary" id="ai-install" ${job.status==='running'||!d.platform_supported||!d.local_models.some(m=>m.eligible)?'disabled':''}>${job.status==='running'?'Setting up…':'Download and set up selected model'}</button>
  <div id="ai-setup-progress" aria-live="polite"><p>${esc(job.stage||'Select a model to begin.')}</p>${job.status==='running'?`<progress max="100" value="${Number(job.percent)||0}" aria-label="Current setup stage progress"></progress><span> ${Number(job.percent)||0}% of current stage</span>`:''}${job.total_bytes?`<p class="detail-caption">${(job.downloaded_bytes/1e9).toFixed(2)} / ${(job.total_bytes/1e9).toFixed(2)} GB</p>`:''}${job.status==='failed'?'<p class="detail-caption">You can retry the setup. Previously downloaded model layers can be reused.</p>':''}</div>
  </div></section>
  <section id="ai-cloud-panel" ${local?'hidden':''} class="card"><div class="card-head"><h2>2. Connect a cloud provider</h2></div><div class="card-body">
  <div class="form-field"><label class="field-label" for="ai-provider">Provider</label><select id="ai-provider" class="filter-select">${d.providers.map(p=>`<option value="${esc(p.id)}" ${cfg.provider===p.id?'selected':''}>${esc(p.label)}</option>`).join('')}</select></div>
  <p class="detail-caption">Five supported provider choices. Models are fetched from your account rather than assumed to be available. An app subscription may not include API credit.</p>
  <p><a id="ai-key-link" target="_blank" rel="noopener noreferrer">Get an API key from the selected provider ↗</a></p>
  <div class="form-field"><label class="field-label" for="ai-api-key">API key</label><input type="password" id="ai-api-key" autocomplete="off" spellcheck="false" placeholder="Paste the provider API key"><small>Your key is never returned by the server or included in review exports.</small></div>
  <label class="ai-consent"><input type="checkbox" id="ai-remember"> Remember in this operating system’s secure credential store, if available</label>
  <button class="button primary" id="ai-cloud-connect">Check key and list available models</button><span id="ai-cloud-status" role="status"></span>
  <div id="ai-cloud-models" hidden><div class="form-field"><label class="field-label" for="ai-cloud-model">Available text model</label><select id="ai-cloud-model" class="filter-select"></select></div><p class="detail-caption">After saving, use “Test selected model” to check a sample response. This may incur a small API charge. No research papers are sent by setup.</p><button class="button primary" id="ai-cloud-save">Use this cloud model</button></div>
  <button class="button soft" id="ai-forget-key">Forget this provider’s saved key</button>
  </div></section>`;
  const bind=(id,fn)=>$(id).addEventListener('click',async e=>{try{await fn(e.currentTarget);}catch(err){toast(err.message,true);}});
  const mode=cloud=>{$('#ai-local-panel').hidden=cloud;$('#ai-cloud-panel').hidden=!cloud;$('#ai-local-mode').classList.toggle('selected',!cloud);$('#ai-cloud-mode').classList.toggle('selected',cloud);};
  $$('input[name="ai-local-model"]').forEach(input=>input.addEventListener('change',()=>{$('#ai-license').checked=false;}));
  bind('#ai-local-mode',()=>mode(false));bind('#ai-cloud-mode',()=>mode(true));
  bind('#ai-rescan',()=>window.renderAISettings());
  bind('#ai-disable',async()=>{await api('/api/ai-settings',{action:'off'});await window.renderAISettings();});
  bind('#ai-install',async b=>{const model=$('input[name="ai-local-model"]:checked')?.value;if(!model)throw Error('Choose a model first.');if(!$('#ai-license').checked)throw Error('Review and accept the selected model license first.');b.disabled=true;try{drawAISettings(await api('/api/ai-settings',{action:'local-setup',model,accept_license:true}));}catch(e){b.disabled=false;throw e;}});
  bind('#ai-connection-test',async b=>{b.disabled=true;$('#ai-test-result').textContent='Testing a sample question…';try{const result=await api('/api/ai-settings',{action:'test'});$('#ai-test-result').textContent=`Connected · ${result.model} · ${result.proposal_count} sample proposals (unapproved)`;}finally{b.disabled=false;}});
  const provider=()=>$('#ai-provider').value;
  const updateProvider=()=>{const p=d.providers.find(p=>p.id===provider());$('#ai-key-link').href=p.keys;$('#ai-api-key').value='';$('#ai-cloud-models').hidden=true;$('#ai-cloud-status').textContent='';};
  $('#ai-provider').addEventListener('change',updateProvider);updateProvider();
  bind('#ai-cloud-connect',async b=>{b.disabled=true;$('#ai-cloud-status').textContent='Checking provider access…';try{const result=await api('/api/ai-settings',{action:'cloud-models',provider:provider(),key:$('#ai-api-key').value,remember:$('#ai-remember').checked});$('#ai-api-key').value='';$('#ai-cloud-model').innerHTML=result.models.map(m=>`<option value="${esc(m.id)}">${esc(m.label)}</option>`).join('');$('#ai-cloud-models').hidden=false;$('#ai-cloud-status').textContent=result.warning||`Connected. Key stored for ${result.key_storage==='system'?'this device in its secure credential store':'this session only'}.`;}finally{b.disabled=false;}});
  bind('#ai-cloud-save',async()=>{drawAISettings(await api('/api/ai-settings',{action:'cloud-save',provider:provider(),model:$('#ai-cloud-model').value}));toast('Cloud model selected. Test it before use.');});
  bind('#ai-forget-key',async()=>{const result=await api('/api/ai-settings',{action:'forget-key',provider:provider()});drawAISettings(result);toast(result.credential_warning||'Provider key removed.',Boolean(result.credential_warning));});
  if(job.status==='running')aiSetupTimer=setTimeout(async()=>{if(S.page!=='settings')return;try{drawAISettings(await api('/api/ai-settings'));}catch(e){toast(e.message,true);}},1800);
}

async function runSelectedAI(){
 if(!S.evidence?.requests?.length)throw Error('Prepare an AI request first.');
 const d=await api('/api/ai-settings'),cfg=d.config;
 if(cfg.mode==='off')throw Error('Open Settings and choose a model first.');
 const cloud=cfg.mode==='cloud';
 showModal('Run your selected AI model.',`Selected: ${cfg.model}. The saved packet contains source text and review instructions. Results stay pending human review.`,
 `<div class="form-field"><label class="field-label" for="saved-ai-request">Saved request</label><select id="saved-ai-request" name="request_id">${S.evidence.requests.map(r=>`<option value="${r.id}">Request ${r.id} · ${esc(r.task)} · ${esc(r.record_id||'review')}</option>`).join('')}</select></div>`+
 (cloud?'<label class="ai-consent"><input type="checkbox" name="allow_external" required> I agree to send this saved packet, including its source text, to the selected cloud provider. API charges may apply.</label>':'<p>The configured model will process this packet locally.</p>'),
 'Run model',async data=>{const review=S.review;const job=await submitAIRequest(()=>api('/api/evidence-run',{review_id:S.review,request_id:Number(data.get('request_id')),selected_provider:cfg.provider,selected_model:cfg.model,allow_external:cloud&&data.get('allow_external')==='on'}),'evidence',review,cfg.model);toast('AI generation started. Proposals will require your review.');});
}
