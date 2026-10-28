'use strict';
window.renderQuestions=async function(){
  const id=S.review;
  const [d,settings,catalog]=await Promise.all([api(endpoint('questions')),api('/api/ai-settings'),api('/api/question-frameworks')]);
  if(S.page!=='questions'||id!==S.review)return;
  const current=d.current?.content.draft||{topic:S.data.review.name,questions:[S.data.review.question]};
  const selected=settings.config;
  const decisions=new Map(d.history.filter(r=>r.kind==='decision').map(r=>[r.content.proposal_sequence+':'+r.content.index,r.content]));
  const proposals=d.history.filter(r=>r.kind==='proposal');
  $('#main').innerHTML=heading('Shape the question.','Your topic, your decisions, and an inspectable record of how they evolve.')+nextStage('questions',{approved:!!d.approved})+`
  <div class="notice"><span>${esc(d.notice)} Local researcher names are recorded labels, not verified identities.</span></div>
  <div class="toolbar"><label>Researcher <select id="question-actor">${[...S.data.reviewers,S.data.adjudicator].map(a=>`<option ${a===S.actor?'selected':''}>${esc(a)}</option>`).join('')}</select></label><button class="button soft" id="question-export">Download revision & AI-use record</button><span class="pill ${d.approved?'green':'orange'}">${d.approved?'Current version approved':'Draft · approval required'}</span></div>
  <section class="card"><div class="card-head"><h2>1. Write or revise your draft</h2></div><div class="card-body">
  <p>Enter your topic and one question per line. A topic alone is enough to request candidate questions. Edit or remove questions here before final approval.</p>
  <label for="question-topic">Research topic <span class="required-marker" aria-label="required to save">*</span></label><textarea id="question-topic" aria-required="true" maxlength="2000" rows="2">${esc(current.topic)}</textarea>
  <label for="question-draft">Research questions · one per line <span class="required-marker" aria-label="required for approval">*</span> (required for approval; optional when generating candidates)</label><textarea id="question-draft" rows="6">${esc(current.questions.join('\n'))}</textarea>
  <div class="toolbar"><button class="button primary" id="question-save">Save draft</button><button class="button green" id="question-approve" ${!d.current||d.approved||!current.questions.length?'disabled':''}>Approve topic and research questions</button></div>
  <p class="detail-caption">Saving changes creates a new version requiring approval. Continue to Review protocol for section approvals and pilot review before a main search.</p></div></section>
  ${frameworkEditor(d,catalog)}
  <section class="card"><div class="card-head"><h2>2. Optional AI assistance</h2><a href="#settings?review=${encodeURIComponent(id)}">AI settings</a></div><div class="card-body">
  <p>${selected.mode==='off'?'AI is off. Configure a model in Settings, or continue manually.':`Selected model: ${esc(selected.provider)} · ${esc(selected.model)}`}</p>
  <p>LitAtlas supplies the instructions. Only the saved topic and questions are sent with those instructions. This action does not browse the internet or establish that a question is novel.</p>
  <label class="ai-consent"><input type="checkbox" id="question-ai-optin"> Enable AI for this request${selected.mode==='cloud'?' and send my saved topic/questions to '+esc(selected.provider)+' (provider charges may apply)':''}.</label>
  <div class="toolbar"><button class="button soft" id="question-generate" ${!d.current||selected.mode==='off'?'disabled':''}>Generate candidate questions</button><button class="button soft" id="question-refine" ${!d.current||!current.questions.length||selected.mode==='off'?'disabled':''}>Refine my draft questions</button></div>
  <div id="question-job" role="status"></div></div></section>
  <section class="card"><div class="card-head"><h2>3. Review individual suggestions</h2></div><div class="card-body">
  <p>Choose whether to add a candidate or replace an existing question. Replaced wording remains in history. Accepting suggestions never grants final approval.</p>
  ${proposals.map(p=>{const req=d.history.find(r=>r.kind==='request'&&r.content.packet.request_id===p.content.envelope.request_id);return `<details open><summary>${esc(p.content.envelope.provider)} · ${esc(p.content.envelope.model)} · ${esc(p.created_utc)}</summary><div class="question-comparison"><div><h3>Original input for this request</h3><p class="question-text">${esc(req.content.packet.packet.draft.topic)}\n${esc(req.content.packet.packet.draft.questions.join('\n'))}</p></div><div><h3>Proposals</h3>${p.content.envelope.output.items.map((item,i)=>{const choice=decisions.get(p.sequence+':'+i);return `<article class="question-suggestion"><span class="pill">${esc(item.field)}</span><p class="question-text">${esc(item.text)}</p><p class="muted">${esc(item.rationale)}</p>${choice?`<p>Recorded decision: ${esc(choice.decision)}</p>`:`${item.field==='question'?`<label>Apply question as<select id="question-target-${p.sequence}-${i}"><option value="add">Add a candidate question</option>${current.questions.map((q,n)=>`<option value="${n}">Replace question ${n+1}: ${esc(q.slice(0,90))}</option>`).join('')}</select></label>`:''}<label>Optional edited wording<textarea id="question-edit-${p.sequence}-${i}" maxlength="2000" rows="3">${esc(item.text)}</textarea></label><div class="toolbar">${['accept','edit','reject'].map(a=>`<button class="button soft small" data-question-proposal="${p.sequence}" data-question-index="${i}" data-question-decision="${a}">${a==='edit'?'Use edited wording':pretty(a)}</button>`).join('')}</div>`}</article>`;}).join('')||'<p>No candidate suggestions returned.</p>'}</div></div></details>`;}).join('')||'<p>No AI proposals recorded. The manual workflow remains available.</p>'}
  </div></section><section class="card"><div class="card-head"><h2>Revision and approval history</h2></div><div class="card-body">${d.history.map(r=>`<details><summary>#${r.sequence} · ${esc(r.kind)} · ${esc(r.actor)} · ${esc(r.created_utc)}</summary><pre class="question-history">${esc(JSON.stringify(r.content,null,2))}</pre></details>`).join('')||'<p>Save your first draft to start its history.</p>'}</div></section>`;
  const values=()=>({topic:$('#question-topic').value.trim(),questions:$('#question-draft').value.split('\n').map(x=>x.trim()).filter(Boolean)});
  const wordingDirty=()=>{const v=values();return v.topic!==current.topic||JSON.stringify(v.questions)!==JSON.stringify(current.questions);};
  let frameworkDirty=()=>false;
  const dirty=()=>wordingDirty()||frameworkDirty();
  const updateNext=()=>{const next=$('.workflow-next');if(next){next.setAttribute('aria-disabled',String(dirty()));next.onclick=ev=>{if(dirty()){ev.preventDefault();toast('Save and approve your edited questions before continuing.',true);}};}};
  $('#question-topic').addEventListener('input',updateNext);$('#question-draft').addEventListener('input',updateNext);
  window.aiUnsavedDraft={review:id,page:'questions',dirty};
  paintAIActivity();
  const send=async body=>{
    const result=await api('/api/questions',{review_id:id,ledger_id:S.data.ledger_id,actor:$('#question-actor').value,expected_revision:d.revision,...body});
    return result;
  };
  const perform=fn=>async()=>{try{await fn();}catch(e){toast(e.message,true);}};
  frameworkDirty=bindFrameworkEditor(d,catalog,send,perform,wordingDirty);
  $('#question-framework-section').addEventListener('input',updateNext);
  $('#question-framework-section').addEventListener('change',updateNext);
  $('#question-actor').onchange=e=>{S.actor=e.target.value;};
  $('#question-save').onclick=perform(async()=>{await send({action:'save',...values(),...(frameworkDirty()?{maps:frameworkDirty.values()}:{})});await window.renderQuestions();});
  $('#question-approve').onclick=perform(async()=>{if(dirty())throw Error('Save your edited draft before approval.');await send({action:'approve'});await window.renderQuestions();$('.workflow-guidance')?.scrollIntoView({behavior:'smooth',block:'start'});});
  $('#question-export').onclick=perform(async()=>{const record=await api(endpoint('questions-export'));const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='ai-assistance-and-revision-record.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  const request=mode=>perform(async()=>{
    if(dirty())throw Error('Save your edited draft before requesting AI suggestions.');
    if(!$('#question-ai-optin').checked)throw Error('Enable AI for this request before continuing.');
    const job=await submitAIRequest(()=>send({action:'request',mode,selected_provider:selected.provider,selected_model:selected.model,allow_external:selected.mode==='cloud'}),'questions',id,selected.model);
    $('#question-job').textContent='AI request started. Follow the activity indicator above; use Show suggestions when ready.';
  });
  $('#question-generate').onclick=request('generate');$('#question-refine').onclick=request('refine');
  document.querySelectorAll('[data-question-decision]').forEach(b=>b.onclick=perform(async()=>{
    if(dirty())throw Error('Save or discard editor changes before deciding on a suggestion.');
    const target=$('#question-target-'+b.dataset.questionProposal+'-'+b.dataset.questionIndex)?.value||'add';
    await send({action:'decision',proposal_sequence:Number(b.dataset.questionProposal),index:Number(b.dataset.questionIndex),decision:b.dataset.questionDecision,operation:target==='add'?'add':'replace',target_index:target==='add'?null:Number(target),text:$('#question-edit-'+b.dataset.questionProposal+'-'+b.dataset.questionIndex).value});await window.renderQuestions();
  }));
};
