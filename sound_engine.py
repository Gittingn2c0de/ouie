#!/usr/bin/env python3
"""Superlarynx UI Sound Engine - run: python sound_engine.py"""
import json, re, html, threading, webbrowser, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from superlarynx.models import PhysicsMode, Seed, Experience, PerceptualEvaluation, PerceptualSpec, CausalHypothesis
from superlarynx.acoustic_graph import AcousticGraph
from superlarynx.compiler import compile_graph_to_recipe
from superlarynx.agents import AGENT_PROMPTS
from superlarynx.ripwave import RipwaveField
import os

ripwave_field = RipwaveField()

PORT = int(os.environ.get("PORT", 8765))
API = 'https://api.inceptionlabs.ai/v1/chat/completions'
MODEL = 'mercury-2.5'
UA = {'User-Agent': 'Mozilla/5.0 sound-engine'}

def http(url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype='application/json'):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == '/':
            self.send(200, PAGE, 'text/html; charset=utf-8')
        elif self.path == '/api/prompts':
            self.send(200, json.dumps(AGENT_PROMPTS))
        else:
            self.send(404, '{}')

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length > 0 else b'{}'
            d = json.loads(body)
        except Exception:
            d = {}

        if self.path == '/api/test_timeout':
            import time
            delay_type = d.get('type', 'read_timeout')
            if delay_type == 'read_timeout':
                time.sleep(2)
                return self.send(502, json.dumps({'error': 'READ_TIMEOUT: simulated'}))
            elif delay_type == '502':
                return self.send(502, json.dumps({'error': 'Bad Gateway'}))
            return self.send(200, json.dumps({"test": "ok"}))

        if self.path == '/api/llm':
            payload = {'model': MODEL, 'messages': d['messages'], 'reasoning_effort': 'low',
                       'temperature': d.get('temperature', 0.6), 'max_completion_tokens': 4096}
            connect_timeout = d.get('connect_timeout', 15000) / 1000.0
            read_timeout = d.get('read_timeout', 25000) / 1000.0
            stage_name = d.get('stage_name', 'unknown')
            import time
            start_time = time.time()
            try:
                r = http(API, json.dumps(payload).encode(), {'Content-Type': 'application/json',
                         'Authorization': 'Bearer ' + d.get('key', '')}, timeout=connect_timeout + read_timeout)
                print(f"[{stage_name}] HTTP 200, dur: {time.time() - start_time:.2f}s")
                return self.send(200, r)
            except urllib.error.HTTPError as e:
                print(f"[{stage_name}] HTTP {e.code}, dur: {time.time() - start_time:.2f}s")
                return self.send(e.code, json.dumps({'error': e.read().decode('utf-8', 'replace')[:300]}))
            except Exception as e:
                msg = str(e)
                dur = time.time() - start_time
                print(f"[{stage_name}] Exception: {msg}, dur: {dur:.2f}s")
                if "timed out" in msg.lower():
                    if dur > connect_timeout:
                        msg = "READ_TIMEOUT: " + msg
                    else:
                        msg = "CONNECT_TIMEOUT: " + msg
                return self.send(502, json.dumps({'error': msg[:300]}))

        if self.path == '/api/compile':
            try:
                graph_dict = d.get('graph', {})
                seed_val = d.get('seed', 42)
                
                # Pre-flight validation
                validation_errors = AcousticGraph.validate_dict(graph_dict)
                if validation_errors:
                    return self.send(400, json.dumps({
                        'error': 'GRAPH_VALIDATION_ERROR',
                        'details': validation_errors
                    }))

                graph = AcousticGraph.from_dict(graph_dict)
                recipe = compile_graph_to_recipe(graph, Seed(value=seed_val))
                return self.send(200, json.dumps(recipe))
            except Exception as e:
                return self.send(400, json.dumps({'error': str(e)}))
                
        if self.path == '/api/ripwave/route':
            routing = ripwave_field.route({}, "", d.get('context', ''))
            return self.send(200, json.dumps(routing))
            
        if self.path == '/api/ripwave/store':
            exp = Experience(user_intent=d.get("intent", ""))
            exp.outcome = d.get("outcome", "neutral")
            eval_data = d.get("evaluation", {})
            exp.evaluation = PerceptualEvaluation(
                user_preference=eval_data.get("preference", 0.0),
                perceptual_similarity=eval_data.get("similarity", 0.5)
            )
            
            # Important: Distinguish infrastructure failure from acoustic failure
            if d.get("infrastructure_error"):
                # Do not feed infrastructure errors into Ripwave as negative experiences
                return self.send(200, json.dumps({"status": "ignored_infra_error"}))

            ripwave_field.store_experience(exp)
            breathe_report = ripwave_field.breathe_inspect()
            return self.send(200, json.dumps({"status": "ok", "breathe": breathe_report}))

        self.send(404, '{}')


PAGE = r'''<!doctype html><html><head><meta charset="utf-8"><title>Superlarynx Engine</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0b0b10;--card:#14141c;--ink:#e8e8f0;--mut:#8a8aa0;--a:#00d9ff;--b:#5a189a;--line:#262633}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif;padding:24px;max-width:860px;margin:auto}
h1{font-size:20px;margin:0 0 4px}h1 span{color:var(--a)}p.s{color:var(--mut);margin:0 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:12px}
input,textarea{width:100%;background:#0e0e15;border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:9px;font:inherit}
textarea{min-height:60px;resize:vertical}label{font-size:12px;color:var(--mut);display:block;margin:8px 0 3px}
button{background:linear-gradient(90deg,var(--b),#0a7a99);color:#fff;border:0;border-radius:8px;padding:9px 16px;font:inherit;cursor:pointer}
button.g{background:#1c1c28;border:1px solid var(--line)}button:disabled{opacity:.5}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.row>*{flex:0 0 auto}
.st{font-size:13px;margin:4px 0}.st b{color:var(--a)}.st.err{color:#ff6b6b}.st.warn{color:#ffb86c}
details{font-size:12px;color:var(--mut);margin:2px 0; background: #0e0e15; padding: 6px; border-radius: 6px; border: 1px solid var(--line);}
pre{white-space:pre-wrap;word-break:break-word;background:#0b0b10;padding:8px;border-radius:8px;max-height:220px;overflow:auto}
canvas{width:100%;height:90px;background:#0e0e15;border-radius:8px;display:block}
summary{cursor:pointer; font-weight: bold; color: var(--a);}
</style></head><body>
<h1>Superlarynx <span>Engine</span></h1><p class="s">Perceptual acoustic synthesis instrument.</p>

<div class="card">
<label>Inception API key</label><input id="key" type="password" placeholder="paste key, then it is remembered locally">
<details><summary>Settings & Timeouts</summary>
<label>SABLE Critic Iterations (max)</label><input id="iters" type="number" value="1" min="1" max="3">
<label>Brand sonic profile</label><textarea id="profile" placeholder="e.g. Calm fintech app..."></textarea>
<label>Connect Timeout (ms)</label><input id="LLM_CONNECT_TIMEOUT_MS" type="number" value="15000">
<label>Read Timeout (ms)</label><input id="LLM_READ_TIMEOUT_MS" type="number" value="25000">
<label>Stage Timeout (ms)</label><input id="LLM_STAGE_TIMEOUT_MS" type="number" value="60000">
</details>
</div>

<div class="card">
<label>What do you need?</label>
<textarea id="prompt" placeholder="e.g. the sound of a marble hitting granite"></textarea>
<div class="row" style="margin-top:10px"><button id="go">Generate</button><button id="cancel" class="g" disabled>Cancel</button><span id="msg" class="st"></span></div>
</div>

<div id="log" class="card" style="display:none"></div>

<div id="res" class="card" style="display:none">
<details><summary>Diagnostic Trace</summary><pre id="diag_out"></pre></details>
<canvas id="cv" width="800" height="90"></canvas>
<div class="row" style="margin-top:10px">
<button id="play">&#9654; Play</button>
<button id="dl" class="g">Download WAV</button><button id="up" class="g">&#128077; Good</button><button id="down" class="g">&#128078; Bad</button>
</div>
<details><summary>SABLE Critique</summary><pre id="sable_out"></pre></details>
<details><summary>Causal Hypothesis</summary><pre id="hypothesis"></pre></details>
<details><summary>Acoustic Graph</summary><pre id="graph_out"></pre></details>
<details><summary>Perceptual Features</summary><pre id="features_out"></pre></details>
</div>

<script>
let P = {};
fetch('/api/prompts').then(r=>r.json()).then(d=>{ P = d; });

const clamp=(v,lo,hi,d)=>{v=Number(v);return isFinite(v)?Math.min(hi,Math.max(lo,v)):d;};
function parseJSON(t){t=t.trim().replace(/^```(?:json)?/i,'').replace(/```$/,'');const a=t.indexOf('{'),b=t.lastIndexOf('}');if(a<0||b<0)throw new Error('no JSON object');return JSON.parse(t.slice(a,b+1));}

function extractFeatures(buf) {
  const d = buf.getChannelData(0);
  let peak = 0, rmsSq = 0, zcr = 0;
  for(let i=0; i<d.length; i++) {
    peak = Math.max(peak, Math.abs(d[i]));
    rmsSq += d[i]*d[i];
    if(i>0 && ((d[i]>=0 && d[i-1]<0) || (d[i]<0 && d[i-1]>=0))) zcr++;
  }
  return { peak: peak, rms: Math.sqrt(rmsSq/d.length), zero_crossing_rate: zcr / (d.length / buf.sampleRate), duration: buf.length / buf.sampleRate };
}

function impulse(ctx,dec){const n=Math.floor(ctx.sampleRate*dec),b=ctx.createBuffer(2,n,ctx.sampleRate);for(let c=0;c<2;c++){const d=b.getChannelData(c);for(let i=0;i<n;i++)d[i]=(Math.random()*2-1)*Math.pow(1-i/n,3);}return b;}
async function render(rc){
  if(!rc.layers) throw new Error("[ACOUSTIC] Invalid recipe");
 const SR=44100,end=Math.max(rc.duration,...rc.layers.map(l=>l.start+l.dur+l.r)),len=end+((rc.reverb&&rc.reverb.mix>0)?rc.reverb.decay:0.05);
 const ctx=new OfflineAudioContext(2,Math.ceil(SR*len),SR);
 const master=ctx.createGain();master.gain.value=0.8;master.connect(ctx.destination);
 const dry=ctx.createGain(),wet=ctx.createGain(),bus=ctx.createGain();
 const rMix = rc.reverb ? rc.reverb.mix : 0.0, rDec = rc.reverb ? rc.reverb.decay : 0.5;
 dry.gain.value=1-rMix;wet.gain.value=rMix;
 dry.connect(master);if(rMix>0){const cv=ctx.createConvolver();cv.buffer=impulse(ctx,rDec);wet.connect(cv);cv.connect(master);}
 bus.connect(dry);bus.connect(wet);
 for(const l of rc.layers){const t0=l.start,t1=t0+l.dur,te=Math.max(t0+l.a+l.d,t1),stop=te+l.r+0.05;let src;
  if(l.type==='noise'){const b=ctx.createBuffer(1,Math.ceil(SR*(stop-t0+0.1)),SR),dd=b.getChannelData(0);for(let i=0;i<dd.length;i++)dd[i]=Math.random()*2-1;src=ctx.createBufferSource();src.buffer=b;}
  else{src=ctx.createOscillator();src.type=l.wave;src.frequency.setValueAtTime(l.f0,t0);src.frequency.exponentialRampToValueAtTime(l.f1,t1);
   if(l.type==='fm'){const m=ctx.createOscillator(),mg=ctx.createGain();m.frequency.setValueAtTime(l.f0*l.fm_ratio,t0);m.frequency.exponentialRampToValueAtTime(l.f1*l.fm_ratio,t1);
    mg.gain.setValueAtTime(l.f0*l.fm_index,t0);mg.gain.exponentialRampToValueAtTime(Math.max(1,l.f1*l.fm_index),t1);m.connect(mg);mg.connect(src.frequency);m.start(t0);m.stop(stop);}}
  const g=ctx.createGain(),pk=l.gain,sus=Math.max(0.0001,pk*l.s);
  g.gain.setValueAtTime(0.0001,t0);g.gain.linearRampToValueAtTime(pk,t0+l.a);g.gain.linearRampToValueAtTime(sus,t0+l.a+l.d);
  g.gain.setValueAtTime(sus,te);g.gain.exponentialRampToValueAtTime(0.0001,te+l.r);
  let node=src;if(l.filter){const f=ctx.createBiquadFilter();f.type=l.filter.type;f.Q.value=l.filter.q;f.frequency.setValueAtTime(l.filter.f0,t0);f.frequency.exponentialRampToValueAtTime(l.filter.f1,t1);node.connect(f);node=f;}
  const p=ctx.createStereoPanner();p.pan.value=l.pan||0;node.connect(g);g.connect(p);p.connect(bus);src.start(t0);src.stop(stop);}
 const buf=await ctx.startRendering();let pk=0;
 for(let c=0;c<2;c++){const d=buf.getChannelData(c);for(let i=0;i<d.length;i++)pk=Math.max(pk,Math.abs(d[i]));}
 const sc=pk>0?0.89/pk:1,fade=Math.floor(SR*0.005);
 for(let c=0;c<2;c++){const d=buf.getChannelData(c);for(let i=0;i<d.length;i++){d[i]*=sc;if(i>d.length-fade)d[i]*=(d.length-i)/fade;}}
 return buf;}

function wav(buf){const n=buf.length,d=new DataView(new ArrayBuffer(44+n*4)),s=(o,t)=>[...t].forEach((c,i)=>d.setUint8(o+i,c.charCodeAt(0)));
 s(0,'RIFF');d.setUint32(4,36+n*4,true);s(8,'WAVEfmt ');d.setUint32(16,16,true);d.setUint16(20,1,true);d.setUint16(22,2,true);d.setUint32(24,buf.sampleRate,true);d.setUint32(28,buf.sampleRate*4,true);d.setUint16(32,4,true);d.setUint16(34,16,true);s(36,'data');d.setUint32(40,n*4,true);
 let o=44;const L=buf.getChannelData(0),R=buf.getChannelData(1);for(let i=0;i<n;i++){d.setInt16(o,Math.max(-1,Math.min(1,L[i]))*32767,true);o+=2;d.setInt16(o,Math.max(-1,Math.min(1,R[i]))*32767,true);o+=2;}return new Blob([d],{type:'audio/wav'});}

const $=id=>document.getElementById(id),LS=localStorage;
['key','profile','iters','LLM_CONNECT_TIMEOUT_MS','LLM_READ_TIMEOUT_MS','LLM_STAGE_TIMEOUT_MS'].forEach(i=>{
  $(i).value=LS.getItem('se_'+i)||($(i).value);
  $(i).addEventListener('input',()=>LS.setItem('se_'+i,$(i).value));
});
const AC=new(window.AudioContext||window.webkitAudioContext)();let cur=null,last={};
let currentController = null;
let diagnostics = { generation_id: "", stages: [] };

async function llm(agent, system, user, temp = 0.6, onRetry = null) {
  const key = $('key').value.trim();
  if (!key) throw new Error('Paste your API key first');

  let m = [{ role: 'system', content: system }, { role: 'user', content: user }];
  let attempts = 0;
  const maxRetries = 3;
  const connectMs = parseInt($('LLM_CONNECT_TIMEOUT_MS').value);
  const readMs = parseInt($('LLM_READ_TIMEOUT_MS').value);
  
  while (attempts < maxRetries) {
    attempts++;
    if(attempts > 1 && onRetry) onRetry(attempts);
    const startTime = Date.now();
    let timeoutCat = null, status = 0, elapsed = 0;
    
    // Explicit timeouts via AbortController
    const controller = new AbortController();
    if(currentController && currentController.signal.aborted) throw new Error("[INFRASTRUCTURE] Cancelled by user");
    currentController = controller;
    
    const id = setTimeout(() => {
      timeoutCat = "READ_TIMEOUT";
      controller.abort();
    }, readMs + connectMs);

    try {
      const r = await fetch('/api/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, messages: m, temperature: temp, connect_timeout: connectMs, read_timeout: readMs, stage_name: agent }),
        signal: controller.signal
      });
      clearTimeout(id);
      
      status = r.status;
      elapsed = Date.now() - startTime;
      
      if (!r.ok) {
        if ([502, 503, 504].includes(r.status)) {
           console.warn("LLM Error", {stage: agent, start_time: startTime, status, elapsed, retried: true, error: 'upstream_error'});
           if (attempts < maxRetries) {
               await new Promise(res => setTimeout(res, 500 + Math.random() * 500 * Math.pow(2, attempts)));
               continue;
           }
        }
        const err = await r.json();
        throw new Error(typeof err.error === 'string' ? err.error : JSON.stringify(err));
      }

      const d = await r.json();
      const t = d.choices[0].message.content;
      
      // Structured diagnostics logging
      console.log("LLM Diagnostic", {stage: agent, start_time: startTime, model: 'mercury-2.5', status, elapsed, retried: attempts>1});

      try {
        return parseJSON(t);
      } catch (e) {
        m = m.concat([
          { role: 'assistant', content: t },
          { role: 'user', content: 'Invalid JSON (' + e.message + '). Return ONLY the JSON object.' }
        ]);
        continue;
      }
    } catch (e) {
      clearTimeout(id);
      elapsed = Date.now() - startTime;
      const errorName = e.name === "AbortError" ? timeoutCat||"CANCELLED" : e.message;
      console.warn("LLM Diagnostic", {stage: agent, start_time: startTime, model: 'mercury-2.5', status, elapsed, retried: attempts < maxRetries, error: errorName});
      
      if (errorName === "CANCELLED") throw new Error("[INFRASTRUCTURE] Cancelled by user");

      if (errorName === "READ_TIMEOUT" || e.message.includes("CONNECT_TIMEOUT") || e.message.includes("READ_TIMEOUT")) {
         if (attempts < maxRetries) {
             await new Promise(res => setTimeout(res, 500 + Math.random() * 500 * Math.pow(2, attempts)));
             continue;
         }
      }
      if (attempts >= maxRetries) {
          throw new Error(`[INFRASTRUCTURE] ${agent} failed: ${errorName}`);
      }
    }
  }
  throw new Error(`[INFRASTRUCTURE] ${agent} failed after ${maxRetries} retries`);
}

function showStatus(name, state, detail='') {
  const l = $('log'); l.style.display = 'block';
  let id = 'st_' + name.replace(/\s+/g,'_');
  let e = document.getElementById(id);
  if(!e){ e = document.createElement('div'); e.id = id; l.appendChild(e); }
  let cls = 'st';
  let icon = '●';
  if(state === 'success') { icon = '✓'; }
  else if(state === 'error') { icon = '⚠'; cls += ' err'; }
  else if(state === 'warn') { icon = '⚠'; cls += ' warn'; }
  else if(state === 'running' && !detail.includes('Retrying')) { icon = '●'; }
  else if(state === 'running' && detail.includes('Retrying')) { icon = '↻'; }
  
  e.className = cls;
  let htmlStr = `<div style="display:flex; justify-content:space-between; width:250px;"><b>${name}</b><span>${icon} ${detail.replace(/^[●✓⚠↻]\s*/,'')}</span></div>`;
  e.innerHTML = htmlStr;
}

async function stage(name, fn, fallbackFn = null) {
  showStatus(name, 'running', 'Processing');
  const startTime = Date.now();
  let attemptCount = 1;
  let result = null;
  let statusStr = "failed";
  let errorClass = "unknown";
  
  try {
    const o = await fn((att) => { attemptCount = att; showStatus(name, 'running', 'Retrying ('+att+')'); });
    showStatus(name, 'success');
    statusStr = "success";
    result = o;
  } catch (e) {
    errorClass = e.message;
    if (fallbackFn) {
      showStatus(name, 'warn', 'Degraded — fallback used');
      statusStr = "degraded";
      result = fallbackFn();
    } else {
      const isInfra = e.message.includes("[INFRASTRUCTURE]");
      showStatus(name, isInfra ? 'error' : 'warn', isInfra ? 'INFRA ERROR' : 'PIPELINE ERROR');
      diagnostics.stages.push({ name: name.toLowerCase(), status: "failed", duration_ms: Date.now() - startTime, attempt: attemptCount, error_class: errorClass });
      throw e;
    }
  }
  diagnostics.stages.push({
    name: name.toLowerCase(),
    status: statusStr,
    duration_ms: Date.now() - startTime,
    attempt: attemptCount,
    error_class: statusStr !== 'success' ? errorClass : undefined
  });
  return result;
}

async function feedback(preference, infraError=false) {
  await fetch('/api/ripwave/store', {
    method: 'POST', body: JSON.stringify({
      intent: last.prompt, 
      outcome: preference>0?"liked":"rejected", 
      evaluation: {preference: preference},
      infrastructure_error: infraError
    })
  });
}

$('cancel').onclick = () => {
    if(currentController) currentController.abort("CANCELLED");
};

$('go').onclick=async()=>{
 const p=$('prompt').value.trim();if(!p)return;
 $('go').disabled=true; $('cancel').disabled=false;
 $('log').innerHTML=''; $('msg').textContent='';
 const overallStartTime = Date.now();
 const stageTimeoutMs = parseInt($('LLM_STAGE_TIMEOUT_MS').value);

 try{
  diagnostics.generation_id = Math.random().toString(36).substring(2, 15);
  const prof=$('profile').value||'(none)';
  
  // 1. Refiner (Nonessential - Degrade gracefully)
  const spec = await stage('REFINER', 
    (onRetry)=>llm('refiner', P.refiner, 'BRAND PROFILE:\n'+prof+'\n\nUSER REQUEST:\n'+p, 0.6, onRetry),
    () => ({ raw_intent: p, event_type: "compound", feeling_word: "unknown", degraded: true, source: "user_prompt", confidence: "low" })
  );
  
  // 2. Storyteller (Nonessential - Degrade gracefully, reduce context)
  const leanSpec = { intent: spec.raw_intent, event_type: spec.event_type };
  const storyIn = JSON.stringify({perceptual_specification: leanSpec, brand_profile: prof}); 
  const hyp = await stage('STORYTELLER', 
    (onRetry)=>llm('storyteller', P.storyteller, storyIn, 0.6, onRetry),
    () => ({ fallback: true, intent: p, nodes: [], edges: [], degraded: true })
  );
  $('hypothesis').textContent = JSON.stringify(hyp, null, 2);

  let iters = parseInt($('iters').value) || 1;
  let current_graph = null, critique = null;
  
  for(let i=0; i<iters; i++) {
    if (Date.now() - overallStartTime > stageTimeoutMs) {
       showStatus('BUDGET', 'warn', 'TIME EXCEEDED');
       break; // Stop gracefully and use best realization
    }

    // 4. Designer / Compiler
    const designIn = JSON.stringify({causal_hypothesis: hyp, previous_critique: critique});
    const designOut = await stage('GRAPH', (onRetry)=>llm('designer', P.designer, designIn, 0.6, onRetry));
    
    // 5. Python Compilation
    current_graph = designOut.graph;
    const recipe = await stage('COMPILER', async()=>{
      const r = await fetch('/api/compile', {method:'POST', body:JSON.stringify({graph: current_graph})});
      if(!r.ok) throw new Error("[PIPELINE] Compiler failed: "+await r.text());
      return await r.json();
    });
    
    // 6. Render
    cur = await stage('RENDER', async() => await render(recipe));
    
    // 7. Perceptual Analysis
    const feats = extractFeatures(cur);
    $('features_out').textContent = JSON.stringify(feats, null, 2);
    
    // 8. SABLE Critic (Nonessential - sound is already rendered)
    const sableIn = JSON.stringify({ target_spec: spec, generated_features: feats, causal_hypothesis: hyp, compiler_trace: recipe.compiler_trace });
    critique = await stage('SABLE', 
      (onRetry)=>llm('sable', P.sable, sableIn, 0.6, onRetry),
      () => ({ accept: true, degraded: true, reason: "SABLE unavailable — accepting current render" })
    );
    $('sable_out').textContent = JSON.stringify(critique, null, 2);
    
    if(critique.accept) break;
  }
  
  if(!current_graph) throw new Error("[PIPELINE] No valid graph generated before timeout.");
  
  $('graph_out').textContent = JSON.stringify(current_graph, null, 2);
  last = {prompt: p, spec: spec};
  
  $('res').style.display='block';
  $('diag_out').textContent = JSON.stringify(diagnostics, null, 2);
  const cv=$('cv'),g=cv.getContext('2d'),d=cur.getChannelData(0);g.clearRect(0,0,800,90);g.strokeStyle='#00d9ff';g.beginPath();
  for(let x=0;x<800;x++){const s=Math.floor(x/800*d.length);let mx=0;for(let j=s;j<Math.min(d.length,s+Math.ceil(d.length/800));j++)mx=Math.max(mx,Math.abs(d[j]));g.moveTo(x,45-mx*42);g.lineTo(x,45+mx*42);}g.stroke();
  play(cur);
 }catch(e){
  $('msg').className='st err';
  $('msg').textContent=e.message;
  console.error(e);
  if(e.message.includes("[INFRASTRUCTURE]")) {
     feedback(0, true); // Don't feed infra errors into Ripwave
  }
 }
 $('go').disabled=false;
 $('cancel').disabled=true;
};

function play(b){AC.resume();const s=AC.createBufferSource();s.buffer=b;s.connect(AC.destination);s.start();}
$('play').onclick=()=>cur&&play(cur);
$('dl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(wav(cur));a.download='sound.wav';a.click();};
$('up').onclick=()=>{feedback(1);$('up').textContent='saved';};
$('down').onclick=()=>{feedback(-1);$('down').textContent='noted';};
</script></body></html>'''

if __name__ == '__main__':
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    print(f'Superlarynx Engine running at http://localhost:{PORT}  (Ctrl+C to stop)')
    threading.Timer(0.8, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass