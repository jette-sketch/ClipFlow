'use strict';
/* ClipFlow P0 dashboard. Synthetic demo only: no credentials, mutations or production API. */
const state = { view: 'overview', data: null, topic: 'All', query: '' };
const root = document.getElementById('content');
const crumb = document.getElementById('crumb-current');
const VIEWS = { overview: 'Overview', trends: 'Trend Hunter', production: 'Production', publishing: 'Publishing', storage: 'Storage & Retention', health: 'System Health' };

function e(tag, className = '', content = null) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (content !== null && content !== undefined) n.textContent = String(content);
  return n;
}
function append(parent, ...children) { for (const child of children) if (child) parent.appendChild(child); return parent; }
function cell(value, className = '') { return e('td', className, value); }
function fmt(n) { return new Intl.NumberFormat('en-US').format(Number(n || 0)); }
function bytes(n) { const b = Number(n || 0); return b < 1e9 ? `${(b / 1e6).toFixed(1)} MB` : `${(b / 1e9).toFixed(2)} GB`; }
function badge(txt) { const v = String(txt || 'Unknown'); const b = e('span', 'badge ' + (/verified|delivered|ready|eligible|resolved|matched|published/i.test(v) ? 'good' : /unknown|failed|blocked|attention|reconcile|held|high/i.test(v) ? 'bad' : /rendering|queued|processing|dry/i.test(v) ? 'warn' : 'neutral'), v); return b; }
function heading(name, description) {
  const hero = e('div', 'hero');
  const left = e('div');
  append(left, e('div', 'eyebrow', 'P0 · OFFLINE PREVIEW'), e('h1', '', name), e('p', '', description));
  const right = e('div', 'hero-actions'); const refresh = e('button', 'ghost-button', '↻  Refresh demo'); refresh.type = 'button'; refresh.addEventListener('click', load);
  append(right, refresh); append(hero, left, right);
  const warning = e('div', 'demo-banner'); append(warning, e('strong', '', 'SYNTHETIC DATA'), e('span', '', ' This preview is not connected to Neon, n8n, Telegram, Google Drive, YouTube or TikTok. Values below are fictional.'));
  return [hero, warning];
}
function metric(label, value, note, tone = '') {
  const box = e('article', `metric ${tone}`); append(box, e('div', 'metric-label', label), e('div', 'metric-value', value), e('div', 'metric-meta', note)); return box;
}
function panel(title, description, wide = false) {
  const p = e('section', `panel ${wide ? 'large-panel' : ''}`), head = e('div', 'panel-head'), body = e('div', 'panel-body');
  const t = e('div'); append(t, e('h2', 'panel-title', title), e('div', 'panel-desc', description));
  append(head, t); append(p, head, body); return {node:p, body};
}
function table(headers, rows) {
  const wrap = e('div', 'wide-table'); const t = e('table', 'data-table');
  const thead = e('thead'), hrow = e('tr'); for (const h of headers) append(hrow, e('th', '', h)); append(thead,hrow);
  const tbody = e('tbody'); for (const row of rows) { const tr = e('tr'); for (const v of row) append(tr, v instanceof Node ? append(e('td'), v) : cell(v)); append(tbody,tr); }
  append(t, thead, tbody); append(wrap,t); return wrap;
}
function recordList(title, items, description) {
  const p = panel(title, description); const list = e('div', 'health-list');
  for(const x of items) { const row = e('div', 'health-item'); const left = e('div'); append(left, e('div', 'health-name', x.title || x.name), e('div', 'health-desc', x.detail || '')); const right = e('div', 'health-status'); append(right, badge(x.status || x.state || x.severity)); append(row,left,right); append(list,row); }
  append(p.body,list); return p.node;
}
function drawOverview(d) {
  const m = e('div', 'metrics');
  append(m, metric('Trending candidates',fmt(d.summary.trends_found),'Discovered in synthetic period','violet'), metric('Ready drafts',fmt(d.summary.drafts_ready),'Archived assets, demo only','mint'), metric('Verified publications',fmt(d.summary.published_verified),'Examples, not real uploads','blue'), metric('Open incidents',fmt(d.summary.open_incidents),'Synthetic alerts, not real','rose'));
  const grid = e('div', 'dashboard-grid');
  const act = panel('Activity', 'Example research findings and clips over seven days');
  const chart = e('div', 'chart-area'); const high = Math.max(1,...d.activity.flatMap(x=>[Number(x.trends),Number(x.clips)]));
  for(const day of d.activity) { const group = e('div', 'chart-group'); const a=e('div','bar trend'), b=e('div','bar clips'); a.style.height=`${Math.max(2, (Number(day.trends)/high)*100)}%`; b.style.height=`${Math.max(2,(Number(day.clips)/high)*100)}%`; a.title=`${day.day}: ${day.trends} trends`; b.title=`${day.day}: ${day.clips} clips`; append(group,a,b); append(chart,group); }
  append(act.body,chart); const labels=e('div','axis-labels'); for(const d2 of d.activity) append(labels,e('span','',d2.day)); append(act.body,labels);
  const pipe=panel('Pipeline','Example progression through ClipFlow'); const pl=e('div','pipeline');const max=Math.max(...d.pipeline.map(x=>x.count),1);
  for(const x of d.pipeline){const item=e('div','pipe-item'), line=e('div','pipe-line'), track=e('div','pipe-track'),fill=e('div','pipe-fill');append(line,e('span','',x.name),e('strong','',fmt(x.count)));fill.style.width=`${Math.round(x.count/max*100)}%`;append(track,fill);append(item,line,track);append(pl,item);}
  append(pipe.body,pl);append(grid,act.node,pipe.node);
  const lower=e('div','lower-grid'); append(lower,recordList('System connectivity',d.systems,'All external systems are unconnected'),recordList('Recent sample incidents',d.incidents.slice(0,3),'Fictional operations examples'));
  append(root,m,grid,lower);
}
function drawTrends(d) {
  const topics=['All', ...new Set(d.trends.map(x=>String(x.topic)))]; const p=panel('Research results','Illustrative YouTube topic scoping and ranking, no live API calls',true);
  const filter=e('div','filterbar'); const search=e('label','searchbox');const field=e('input');field.type='search';field.placeholder='Filter by title, channel or topic';field.setAttribute('aria-label','Search trend results');field.value=state.query;
  append(search,field);const chips=e('div','subject-tags');
  for(const topic of topics){const b=e('button','topic-chip'+(state.topic===topic?' selected':''),topic);b.type='button';b.addEventListener('click',()=>{state.topic=topic;draw();});append(chips,b);}
  append(filter,search,chips); const place=e('div');const update=()=>{place.replaceChildren();const q=state.query.toLowerCase().trim();const filtered=d.trends.filter(x=>(state.topic==='All'||x.topic===state.topic)&&[x.topic,x.title,x.channel].some(v=>String(v).toLowerCase().includes(q)));append(place,filtered.length?table(['Video','Topic','Channel','Views','Velocity proxy','Scope'],filtered.map(x=>[x.title,x.topic,x.channel,fmt(x.views),`${fmt(x.views_per_hour)}/h`,badge(x.scope)])):e('p','empty','No matching demo results.'));};
  field.addEventListener('input',()=>{state.query=field.value;update();});append(p.body,filter,place);update();append(root,p.node);
}
function drawProduction(d) {
  const p=panel('Clip jobs','Progress and delivery examples. No actual worker connection.',true);
  const rows=d.jobs.map(x=>{const progress=e('div','progress-track');const fill=e('div','progress-fill');fill.style.width=`${Math.min(100,Math.max(0,Number(x.progress)||0))}%`;append(progress,fill);return [x.id,x.title,badge(x.state),progress,x.duration,x.size_mb?`${x.size_mb} MB`:'Not rendered'];});
  append(p.body,table(['Job','Clip','Status','Progress','Duration','Size'],rows));append(root,p.node);
}
function drawPublishing(d) {
  const p=panel('Platform delivery','Synthetic YouTube/TikTok outcomes. Five automatic retries shared per video.',true);
  append(p.body,table(['Clip','Destination','Status','Retry count','Last update'],d.uploads.map(x=>[x.clip,x.platform,badge(x.status),`${x.retries} / ${x.limit} shown (per-clip shared cap)`,x.updated])));
  const hint=e('div','panel-notice','A failed or uncertain platform upload must preserve the Drive draft. Public TikTok posting remains blocked pending official authorization.'); append(p.body,hint);append(root,p.node);
}
function drawStorage(d) {
  const cards=e('div','storage-cards');const sets=[['Google Drive',d.capacity.drive_bytes,d.capacity.drive_quota_bytes],['Neon PostgreSQL',d.capacity.neon_estimate_bytes,d.capacity.neon_quota_bytes],['Local cache',d.capacity.local_cache_bytes,null]];
  for(const [name,used,quota] of sets){const p=e('article','storage-card');append(p,e('div','storage-label',name),e('div','storage-value',bytes(used)),e('div','storage-sub',quota ? `of ${bytes(quota)} example allocation`:'Example local bytes'));const track=e('div','storage-track'), fill=e('div','storage-fill');fill.style.width=quota?`${Math.min(100,Math.round(used/quota*100))}%`:'35%';append(track,fill);append(p,track);append(cards,p);}
  const p=panel('Retention queue','Seven-day policy preview; deletions are NOT enabled.',true);
  append(p.body,table(['Artifact','Kind','Age','Size','Eligibility','Reason'],d.retention.map(x=>[x.id,x.kind,x.age,`${x.size_mb} MB`,badge(x.state),x.reason])));
  append(p.body,e('div','retention-notice','Real cleanup is blocked until account isolation, ownership checks, dry-run readback, and a tested delete executor are verified.'));
  append(root,cards,p.node);
}
function drawHealth(d){append(root,recordList('Service connectivity',d.systems,'Every service is disconnected in this local demo'),recordList('Incident examples',d.incidents,'Synthetic warnings and failures; no real alerts were sent.'));}
function draw() {
  root.replaceChildren(); if (!state.data) {append(root,e('div','loading','Loading demo data…'));return;}
  crumb.textContent=VIEWS[state.view].toUpperCase();append(root,...heading(VIEWS[state.view],'A local read-only preview of the future ClipFlow operations dashboard.'));
  const map={overview:drawOverview,trends:drawTrends,production:drawProduction,publishing:drawPublishing,storage:drawStorage,health:drawHealth};map[state.view](state.data);
  for(const b of document.querySelectorAll('[data-view]')){const active=b.dataset.view===state.view;b.classList.toggle('active',active);b.setAttribute('aria-current',active?'page':'false');}
}
async function load() {
  try {const r=await fetch('/api/v1/dashboard',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const payload=await r.json();if(payload.mode!=='synthetic_demo'||payload.connected!==false)throw Error('Unexpected demo mode');state.data=payload;draw();}
  catch(err){root.replaceChildren();append(root,e('div','demo-banner',`Dashboard preview unavailable: ${err.message}. No external systems were changed.`));}
}
for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>{state.view=b.dataset.view;draw();});
const clock=document.getElementById('localtime');try{clock.textContent=new Intl.DateTimeFormat('en-PH',{timeZone:'Asia/Manila',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date())+' PHT';}catch{clock.textContent='PHT';}
load();
