#!/usr/bin/env python3
"""Superlarynx UI Sound Engine - run: python sound_engine.py"""
import json, re, html, threading, webbrowser, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from superlarynx.models import PhysicsMode, Seed, Experience, PerceptualEvaluation, PerceptualSpec, CausalHypothesis
from superlarynx.acoustic_graph import AcousticGraph
from superlarynx.compiler import compile_graph_to_recipe
from superlarynx.agents import AGENT_PROMPTS
from superlarynx.ripwave import RipwaveField

ripwave_field = RipwaveField()

PORT = 8765
API = 'https://api.inceptionlabs.ai/v1/chat/completions'
MODEL = 'mercury-2.5'
UA = {'User-Agent': 'Mozilla/5.0 sound-engine'}

def http(url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')

def clean(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s)).strip()

def research(queries, fs):
    out, errs = [], []
    for q in queries[:2]:
        try:
            if fs:
                u = 'https://freesound.org/apiv2/search/text/?' + urllib.parse.urlencode({
                    'query': q, 'filter': 'duration:[0 TO 3]', 'page_size': 5, 'token': fs,
                    'fields': 'name,description,tags,duration,license'})
                for s in json.loads(http(u, headers=UA)).get('results', []):
                    out.append({'src': 'freesound', 'name': s['name'], 'tags': s.get('tags', [])[:8],
                                'dur': s.get('duration'), 'license': s.get('license'),
                                'desc': (s.get('description') or '')[:200]})
            else:
                h = http('https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(q + ' sound design'), headers=UA)
                for t, sn in re.findall(r'class="result__a"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>', h, re.S)[:5]:
                    out.append({'src': 'web', 'name': clean(t), 'desc': clean(sn)[:250]})
        except Exception as e:
            errs.append(str(e)[:100])
    return {'results': out, 'errors': errs}

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
        d = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        if self.path == '/api/research':
            return self.send(200, json.dumps(research(d.get('queries', []), d.get('freesound', ''))))
        
        if self.path == '/api/llm':
            payload = {'model': MODEL, 'messages': d['messages'], 'reasoning_effort': 'low',
                       'temperature': d.get('temperature', 0.6), 'max_completion_tokens': 4096}
            try:
                r = http(API, json.dumps(payload).encode(), {'Content-Type': 'application/json',
                         'Authorization': 'Bearer ' + d.get('key', '')}, timeout=90)
                return self.send(200, r)
            except urllib.error.HTTPError as e:
                return self.send(e.code, json.dumps({'error': e.read().decode('utf-8', 'replace')[:300]}))
            except Exception as e:
                return self.send(502, json.dumps({'error': str(e)[:300]}))
                
        if self.path == '/api/compile':
            try:
                graph_dict = d.get('graph', {})
                seed_val = d.get('seed', 42)
                graph = AcousticGraph.from_dict(graph_dict)
                recipe = compile_graph_to_recipe(graph, Seed(value=seed_val))
                return self.send(200, json.dumps(recipe))
            except Exception as e:
                return self.send(400, json.dumps({'error': str(e)}))
                
        if self.path == '/api/ripwave/route':
            routing = ripwave_field.route({}, "", d.get('context', ''))
            return self.send(200, json.dumps(routing))
            
        if self.path == '/api/ripwave/store':
            # Minimal store implementation for feedback
            exp = Experience(user_intent=d.get("intent", ""))
            exp.outcome = d.get("outcome", "neutral")
            eval_data = d.get("evaluation", {})
            exp.evaluation = PerceptualEvaluation(
                user_preference=eval_data.get("preference", 0.0),
                perceptual_similarity=eval_data.get("similarity", 0.5)
            )
            ripwave_field.store_experience(exp)
            # Run BREATHE occasionally
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
.st{font-size:13px;margin:4px 0}.st b{color:var(--a)}.st.err{color:#ff6b6b}
details{font-size:12px;color:var(--mut);margin:2px 0; background: #0e0e15; padding: 6px; border-radius: 6px; border: 1px solid var(--line);}
pre{white-space:pre-wrap;word-break:break-word;background:#0b0b10;padding:8px;border-radius:8px;max-height:220px;overflow:auto}
canvas{width:100%;height:90px;background:#0e0e15;border-radius:8px;display:block}
summary{cursor:pointer; font-weight: bold; color: var(--a);}
</style></head><body>
<h1>Superlarynx <span>Engine</span></h1><p class="s">Perceptual acoustic synthesis instrument.</p>

<div class="card">
<label>Inception API key</label><input id="key" type="password" placeholder="paste key, then it is remembered locally">
<details><summary>Settings</summary>
<label>SABLE Critic Iterations (max)</label><input id="iters" type="number" value="1" min="1" max="3">
<label>Brand sonic profile</label>
<textarea id="profile" placeholder="e.g. Calm fintech app..."></textarea>
</details>
</div>

<div class="card">
<label>What do you need?</label>
<textarea id="prompt" placeholder="e.g. the sound of a marble hitting granite"></textarea>
<div class="row" style="margin-top:10px"><button id="go">Generate</button><span id="msg" class="st"></span></div>
</div>

<div id="log" class="card" style="display:none"></div>

<div id="res" class="card" style="display:none">
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
  return {
    peak: peak,
    rms: Math.sqrt(rmsSq/d.length),
    zero_crossing_rate: zcr / (d.length / buf.sampleRate),
    duration: buf.length / buf.sampleRate
  };
}

function impulse(ctx,dec){const n=Math.floor(ctx.sampleRate*dec),b=ctx.createBuffer(2,n,ctx.sampleRate);for(let c=0;c<2;c++){const d=b.getChannelData(c);for(let i=0;i<n;i++)d[i]=(Math.random()*2-1)*Math.pow(1-i/n,3);}return b;}
async function render(rc){
  if(!rc.layers) throw new Error("Invalid recipe");
 const SR=44100,end=Math.max(rc.duration,...rc.layers.map(l=>l.start+l.dur+l.r)),len=end+((rc.reverb&&rc.reverb.mix>0)?rc.reverb.decay:0.05);
 const ctx=new OfflineAudioContext(2,Math.ceil(SR*len),SR);
 const master=ctx.createGain();master.gain.value=0.8;master.connect(ctx.destination);
 const dry=ctx.createGain(),wet=ctx.createGain(),bus=ctx.createGain();
 const rMix = rc.reverb ? rc.reverb.mix : 0.0;
 const rDec = rc.reverb ? rc.reverb.decay : 0.5;
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
['key','profile','iters'].forEach(i=>{$(i).value=LS.getItem('se_'+i)||($(i).value);$(i).addEventListener('input',()=>LS.setItem('se_'+i,$(i).value));});
const AC=new(window.AudioContext||window.webkitAudioContext)();let cur=null,last={};

async function llm(agent,system,user,temp=0.6){
 const key=$('key').value.trim();if(!key)throw new Error('Paste your API key first');
 let m=[{role:'system',content:system},{role:'user',content:user}];
 for(let i=0;i<2;i++){const r=await fetch('/api/llm',{method:'POST',body:JSON.stringify({key,messages:m,temperature:temp})}),d=await r.json();
  if(!r.ok)throw new Error(agent+': '+(typeof d.error==='string'?d.error:JSON.stringify(d.error||d)));
  const t=d.choices[0].message.content;try{return parseJSON(t);}catch(e){m=m.concat([{role:'assistant',content:t},{role:'user',content:'Invalid JSON ('+e.message+'). Return ONLY the JSON object.'}]);}}
 throw new Error(agent+': no valid JSON after retry');}

function show(name,obj,err){
 const l=$('log');l.style.display='block';let e=document.getElementById('st_'+name.replace(/\s+/g,'_'));
 if(!e){e=document.createElement('div');e.id='st_'+name.replace(/\s+/g,'_');l.appendChild(e);}
 e.className='st'+(err?' err':'');e.innerHTML='<b>'+name+'</b> '+(err?('failed: '+err):(obj?'done':'working...'))+(obj?'<details><summary>output</summary><pre></pre></details>':'');
 if(obj)e.querySelector('pre').textContent=JSON.stringify(obj,null,2);}

async function stage(name,fn,soft){show(name);try{const o=await fn();show(name,o);return o;}catch(e){show(name,null,e.message);if(!soft)throw e;return null;}}

async function feedback(preference) {
  await fetch('/api/ripwave/store', {
    method: 'POST', body: JSON.stringify({
      intent: last.prompt, outcome: preference>0?"liked":"rejected", evaluation: {preference: preference}
    })
  });
}

$('go').onclick=async()=>{
 const p=$('prompt').value.trim();if(!p)return;$('go').disabled=true;$('log').innerHTML='';$('msg').textContent='';
 try{
  const prof=$('profile').value||'(none)';
  
  // 1. Refiner
  const spec = await stage('Refiner', ()=>llm('refiner', P.refiner, 'BRAND PROFILE:\n'+prof+'\n\nUSER REQUEST:\n'+p));
  
  // 2. Ripwave Routing
  const route = await stage('Ripwave Routing', async()=>{
    const r=await fetch('/api/ripwave/route', {method:'POST', body:JSON.stringify({context: p})});
    return await r.json();
  }, true);

  // 3. Storyteller
  const storyIn = JSON.stringify({perceptual_specification: spec, brand_profile: prof, ripwave_hints: route});
  const hyp = await stage('Storyteller', ()=>llm('storyteller', P.storyteller, storyIn));
  $('hypothesis').textContent = JSON.stringify(hyp, null, 2);

  let iters = parseInt($('iters').value) || 1;
  let current_graph = null;
  let critique = null;
  
  for(let i=0; i<iters; i++) {
    // 4. Designer / Compiler
    const designIn = JSON.stringify({causal_hypothesis: hyp, previous_critique: critique});
    const designOut = await stage('Designer (Iter '+(i+1)+')', ()=>llm('designer', P.designer, designIn));
    
    // 5. Python Compilation
    current_graph = designOut.graph;
    const recipe = await stage('Acoustic Compiler (Iter '+(i+1)+')', async()=>{
      const r = await fetch('/api/compile', {method:'POST', body:JSON.stringify({graph: current_graph})});
      if(!r.ok) throw new Error(await r.text());
      return await r.json();
    });
    
    // 6. Render
    cur = await render(recipe);
    
    // 7. Perceptual Analysis
    const feats = extractFeatures(cur);
    $('features_out').textContent = JSON.stringify(feats, null, 2);
    
    // 8. SABLE Critic
    const sableIn = JSON.stringify({
      target_spec: spec, generated_features: feats, causal_hypothesis: hyp
    });
    critique = await stage('SABLE Critic (Iter '+(i+1)+')', ()=>llm('sable', P.sable, sableIn));
    $('sable_out').textContent = JSON.stringify(critique, null, 2);
    
    if(critique.accept) break;
  }
  
  $('graph_out').textContent = JSON.stringify(current_graph, null, 2);
  last = {prompt: p, spec: spec};
  
  $('res').style.display='block';
  const cv=$('cv'),g=cv.getContext('2d'),d=cur.getChannelData(0);g.clearRect(0,0,800,90);g.strokeStyle='#00d9ff';g.beginPath();
  for(let x=0;x<800;x++){const s=Math.floor(x/800*d.length);let mx=0;for(let j=s;j<Math.min(d.length,s+Math.ceil(d.length/800));j++)mx=Math.max(mx,Math.abs(d[j]));g.moveTo(x,45-mx*42);g.lineTo(x,45+mx*42);}g.stroke();
  play(cur);
 }catch(e){$('msg').className='st err';$('msg').textContent=e.message; console.error(e);}
 $('go').disabled=false;
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