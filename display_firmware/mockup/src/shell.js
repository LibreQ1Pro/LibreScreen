// ---- the page around the screens ------------------------------------------------------------------------------------
const GROUPS = [];
SCREENS.forEach(s=>{ if(!GROUPS.includes(s.group)) GROUPS.push(s.group); });
let zoom = 1, showGrid = false, showNames = false;
const VSTATE = {};       // the chosen variant of every screen (gallery)

// the one way to draw a screen: gallery, all languages, screenshots and the audit all come through here; the globals of the
// builders (language, variant, current page) are put back afterwards
function variantOf(sc){ return sc.variants ? (VSTATE[sc.id] || sc.variants[0].id) : ''; }
function renderScreen(sc, langIndex, variantId){
  const sl = lang, sv = VARIANT, sp = CUR;
  try { if (langIndex != null) lang = langIndex; VARIANT = variantId != null ? variantId : variantOf(sc); return sc.build(); }
  finally { lang = sl; VARIANT = sv; CUR = sp; }
}
const FW_BY_NAME = {}; FW_PAGES.forEach(p=>{ FW_BY_NAME[p.key] = p.id; });
// a screen by its (new) id; the old names still work: a stock page name (main, sys_ok ...) and an id of the first gallery (files, printing2 ...)
function findScreen(id){
  return SCREENS.find(x=>x.id===id) || SCREENS.find(x=>x.id===(GALLERY_ALIASES[id] || PAGE_NAMES[id]));
}

function tokensHTML(){
  const sw = (n,v,t)=>`<div class="sw-c"><div style="background:${v}"></div><span><b>${n}</b><br>${v}${t?'<br>'+t:''}</span></div>`;
  return `<h2 id="tokens">Design tokens</h2>
  <p style="color:#9c9aa5;max-width:900px;font-size:13px;line-height:1.5">The screen is 272 × 480, 16-bit colour: flat fills only (no gradients, no shadows: they band). One grid: <b>8 px</b>; page margin <b>12</b>, content width <b>248</b>, gap <b>8</b>; touch targets are at least <b>40</b> high (buttons 44, list rows 46–52, keys 44); corner radius <b>14</b> for cards, <b>10</b> for buttons, <b>8</b> for keys. The navigation bar is 56 high (y 424), the header 48.</p>
  <div class="sw-row">
  ${sw('bg','#181818','page')}${sw('panel','#212021','card')}${sw('card','#292829','card, raised')}${sw('btn','#313039','button')}${sw('btn-hi','#42414a','selected')}${sw('btn-press','#292831','pressed')}
  ${sw('line','#393842','dividers')}${sw('nav','#101010','navigation bar')}${sw('accent','#3979ff','primary, active')}${sw('accent-press','#3161ce','primary pressed')}${sw('danger','#e7494a','stop, forget')}${sw('danger-bg','#4a2429','danger button')}${sw('heat','#ff795a','heater is on')}${sw('ok','#31a26b','done')}${sw('warn','#f7a621','warning')}
  ${sw('text','#f7f7f7','text')}${sw('text2','#a5a6b5','secondary text')}${sw('text3','#6b6d7b','disabled')}
  </div>
  <div class="type-sample"><div class="r-t19">text 19 / 600 — Header, title: Wi-Fi Connection</div>
  <div class="r-t16">text 16 / 500 — Button, body: Please select the nozzle temperature.</div><div class="r-t13" style="color:#a5a6b5">text 13 / 400 — Caption: MAX : 350</div>
  <div class="r-d32">digits 32 / 600 — 220</div><div class="r-d28">digits 28 / 600 — 0123456789 °C %</div><div class="r-d20">digits 20 / 600 — -1.000 / 100 %</div>
  <div style="font-size:16px;margin-top:6px">中文简体 日本語 한국어 العربية עברית Русский Türkçe</div></div>
  <p style="color:#9c9aa5;max-width:900px;font-size:13px">The screen has these six fonts and no others (one size and weight is one font resource, .zi): text 13 / 400, 16 / 500, 19 / 600 and digits 20 / 28 / 32 (all 600; <code>0-9 . - / % ° ℃ + * </code>). The text fonts cover Latin, Cyrillic, Chinese, Japanese, Korean, Arabic and Hebrew only as far as the real strings need them. The preview uses Noto Sans: widths, weights and baselines are provisional until the real fonts are rendered, and the shaping of Arabic and Hebrew is the browser's, not a proof that the screen does it.</p>`;
}
function componentsHTML(){
  CUR='';
  const b=(x,y,w,h,l,o)=>btn(x,y,w,h,l,o);
  const comp = (title,html,w,h)=>`<div class="item"><div class="cap">${title}</div><div class="scr" style="width:${w}px;height:${h}px;background:var(--bg)">${html}</div></div>`;
  let h = `<h2 id="components">Components</h2><div class="grid">`;
  h += comp('Buttons: normal / pressed / primary / danger / dim', b(12,12,110,44,'OK')+b(130,12,110,44,'OK',{press:1})+b(12,64,110,44,'Start',{v:'primary'})+b(130,64,110,44,'Start',{v:'primary',press:1})+b(12,116,110,44,'Stop',{v:'danger'})+b(130,116,110,44,'Back',{v:'dim'})+b(12,168,110,44,'',{icon:'chevron-left',is:24})+b(130,168,110,44,'Wi-Fi',{icon:'wifi'}),252,226);
  h += comp('List rows', row(12,12,228,48,'Language',{chev:1})+row(12,68,228,48,'Setup Guide',{sw:true})+row(12,124,228,48,'5 minutes',{radio:true,sel:true})+row(12,180,228,48,'15 minutes',{radio:false})+row(12,236,228,48,'Home Wi-Fi',{check:true})+row(12,292,228,48,'Neighbour',{lock:true}),252,352);
  h += comp('Tabs, toggles, progress, slider', `<div class="tabs" style="${st(12,12,228,40)}"><div class="tab on" style="${st(3,3,111,34)}">General</div><div class="tab" style="${st(114,3,111,34)}">Calibration</div></div>`+toggle(20,70,true)+toggle(80,70,false)+progress(12,116,228,8,35)+`<div class="radio on" style="left:20px;top:150px"></div><div class="radio" style="left:60px;top:150px"></div>`+slider(12,174,228,60,null,{ticks:[20,40,60,80,100]})+btn(12,230,228,44,'Auto Bed Leveling',{}),252,290);
  h += comp('Keys', ['1','2','3','4','5','6'].map((k,i)=>`<div class="key" style="${st(12+78*(i%3),12+48*Math.floor(i/3),72,42)}">${k}</div>`).join('')+`<div class="key fn" style="${st(12,108,72,42)}">${ico('delete',20)}</div><div class="key" style="${st(90,108,72,42)}">0</div><div class="key" style="${st(168,108,72,42)};background:var(--accent)">${ico('check',22,'#fff',2.5)}</div>`,252,162);
  return h + '</div>';
}
function variantChips(sc){
  if (!sc.variants) return '';
  const cur = variantOf(sc);
  return `<div class="chips">${sc.variants.map(v=>`<a class="chip${v.id===cur?' on':''}" data-s="${sc.id}" data-v="${v.id}">${esc(v.label)}</a>`).join('')}</div>`;
}
function cardHTML(s, z){
  const html = renderScreen(s);
  return `<div class="item" id="s-${s.id}"><div class="cap"><b style="color:#ddd">${s.title}</b><code>${s.id}</code><a data-all="${s.id}">all languages</a></div>${variantChips(s)}`+
    `<div class="zoomwrap" style="width:${272*z}px;height:${480*z}px"><div style="transform:scale(${z});transform-origin:0 0;width:272px;height:480px;position:relative">${html}</div></div>${s.note?`<div class="cap" style="max-width:${272*z}px;white-space:normal;color:#7b7984">${s.note}</div>`:''}</div>`;
}
function render(){
  const main = document.getElementById('main');
  let h = tokensHTML() + componentsHTML();
  GROUPS.forEach((g,gi)=>{
    h += `<h2 id="g${gi}">${g}</h2><div class="grid">` + SCREENS.filter(s=>s.group===g).map(s=>cardHTML(s,zoom)).join('') + '</div>';
  });
  main.innerHTML = h;
  document.body.classList.toggle('showgrid', showGrid);
  document.body.classList.toggle('show-names', showNames);
  document.querySelectorAll('[data-all]').forEach(a=>a.onclick=()=>allLanguages(a.dataset.all));
  document.querySelectorAll('.chip').forEach(a=>a.onclick=()=>{ VSTATE[a.dataset.s] = a.dataset.v; render(); const el=document.getElementById('s-'+a.dataset.s); if(el) el.scrollIntoView({block:'nearest'}); });
}
function langGrid(s, vid){
  let h='';
  for(let i=0;i<LANGS.length;i++){ h+=`<div class="item"><div class="cap">${LANG_NAMES[i]} <code>${LANGS[i]}</code></div><div class="zoomwrap" style="width:${272*zoom}px;height:${480*zoom}px"><div style="transform:scale(${zoom});transform-origin:0 0;width:272px;height:480px;position:relative">${renderScreen(s,i,vid)}</div></div></div>`; }
  return h;
}
function allLanguages(id){
  const s = findScreen(id);
  const m = document.getElementById('modal');
  m.innerHTML = `<div class="box"><h3>${s.title} — all 13 languages <button id="close">Close</button></h3>${variantChips(s)}<div class="langgrid">${langGrid(s)}</div></div>`;
  m.classList.add('on'); document.getElementById('close').onclick=()=>m.classList.remove('on');
  m.querySelectorAll('.chip').forEach(a=>a.onclick=()=>{ VSTATE[a.dataset.s] = a.dataset.v; allLanguages(id); render(); });
}

// ---- the audit -----------------------------------------------------------------------------------------------------------------
// ?audit=1   spacing: the gaps between neighbouring blocks and the margins to the screen edge (informational)
// ?audit=hw  what the screen can do: fonts, text that does not fit, touch regions, fixed slots, coverage of the pages of the project
function spacingAudit(){
  const out = [];
  SCREENS.forEach(sc=>{
    const host = document.createElement('div'); host.style.cssText='position:absolute;left:0;top:0'; host.innerHTML = renderScreen(sc); document.body.appendChild(host);
    const scr = host.querySelector('.scr'); const base = scr.getBoundingClientRect();
    const items = [];
    scr.querySelectorAll('.btn,.card,.key,.thumb,.tabs,.bar,.anim,.popup,.sw,.radio,.rowhit').forEach(el=>{
      if(el.closest('.nav') || el.closest('.btn,.key,.tabs,.popup,.card,.rowhit') && el.closest('.btn,.key,.tabs,.popup,.card,.rowhit')!==el) return;
      const r = el.getBoundingClientRect();
      if(r.width<14 || r.height<8) return;
      items.push({n:(el.dataset.w||el.className.split(' ')[0]).replace(/^[^.]*\./,''), x:Math.round(r.left-base.left), y:Math.round(r.top-base.top), w:Math.round(r.width), h:Math.round(r.height)});
    });
    const gaps = {};
    const add = (axis,g,a,b)=>{ (gaps[axis+g] = gaps[axis+g]||[]).push(a.n+'|'+b.n); };
    for(let i=0;i<items.length;i++) for(let j=0;j<items.length;j++){ if(i===j) continue; const a=items[i], b=items[j];
      const oy = Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y), ox = Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x);
      if(oy>=Math.min(a.h,b.h)*0.5){ const g=b.x-(a.x+a.w); if(g>0 && g<=24) add('H',g,a,b); }
      if(ox>=Math.min(a.w,b.w)*0.5){ const g=b.y-(a.y+a.h); if(g>0 && g<=24) add('V',g,a,b); }
    }
    const margins = items.filter(i=>i.y<424 && (i.w<272)).map(i=>({n:i.n,l:i.x,r:272-(i.x+i.w)})).filter(m=>m.l<30&&m.l>=0&&(m.l!==12||m.r!==12) && !(m.l>=12&&m.r>=12&&m.l+m.r>=24 && (m.l===12||m.r===12)));
    out.push({id:sc.id, items:items.length, gaps:Object.fromEntries(Object.entries(gaps).map(([k,v])=>[k,[...new Set(v)].slice(0,4)])), margins:margins.slice(0,6)});
    host.remove();
  });
  const pre=document.createElement('pre'); pre.id='audit'; pre.textContent=JSON.stringify(out); document.body.appendChild(pre);
}
const _range = el => { const r = document.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect(); };
function hwAudit(){
  const ALLOWED = new Set(Object.values(ROLES).map(r=>r.s+'/'+r.w));
  const host = document.createElement('div'); host.style.cssText='position:absolute;left:0;top:0'; document.body.appendChild(host);
  const found = {};          // grouped problems: key -> {…, langs:[]}
  const report = (kind, sc, vid, l, widget, detail) => {
    const key = [kind, sc.id, vid, widget, detail].join('|');
    (found[key] = found[key] || {kind, screen:sc.id, variant:vid, widget, detail, langs:[]}).langs.push(LANGS[l]);
  };
  const pages = {}; const longNames = new Set(); let renders = 0;
  for (const sc of SCREENS){
    const vids = sc.variants ? sc.variants.map(v=>v.id) : [''];
    vids.forEach((vid,vi)=>{
      for (let l=0; l<LANGS.length; l++){
        host.innerHTML = renderScreen(sc,l,vid); renders++;
        const scr = host.querySelector('.scr'), sr = scr.getBoundingClientRect(), page = scr.dataset.old;     // the stock name: the coverage is checked against project.json
        if (vi === 0 && l === 0) (pages[page] = pages[page] || []).push(sc.id);
        const rel = el => { const r = el.getBoundingClientRect(); return [Math.round(r.x-sr.x), Math.round(r.y-sr.y), Math.round(r.width), Math.round(r.height)]; };
        const label = el => el.dataset.w ? el.dataset.w.replace(/^[^.]*\./,'') : (el.getAttribute('title')||el.className).toString().split('  ')[0].replace(/^[^.]*\./,'') || el.className;
        // 1. fonts: only the six
        scr.querySelectorAll('.t,.btn,.key,.tab,.step,.r-t13').forEach(el=>{
          const cs = getComputedStyle(el), k = parseFloat(cs.fontSize)+'/'+cs.fontWeight;
          if (!ALLOWED.has(k)) report('font', sc, vid, l, label(el), k);
        });
        // 1b. the text of the host (class dyn) is drawn in the one wide font
        scr.querySelectorAll('.dyn').forEach(el=>{
          const cs = getComputedStyle(el), k = parseFloat(cs.fontSize)+'/'+cs.fontWeight, want = ROLES[DYNAMIC_ROLE].s+'/'+ROLES[DYNAMIC_ROLE].w;
          if (k !== want) report('dynamic_font', sc, vid, l, label(el), k+' (the wide font is '+want+')');
        });
        // 2. text that does not fit its widget (a scrolling area is meant to overflow)
        scr.querySelectorAll('.t').forEach(el=>{
          if (el.classList.contains('scroll')) return;
          const sp = el.querySelector(':scope > span'); if (!sp || !sp.textContent.trim()) return;
          const r = el.getBoundingClientRect(), t = _range(sp), extra = 0.17*parseFloat(getComputedStyle(el).fontSize);
          if (t.width > r.width+0.5 || t.height-extra > r.height+0.5) report('text_clipped', sc, vid, l, label(el), Math.round(t.width)+'x'+Math.round(t.height)+' in '+Math.round(r.width)+'x'+Math.round(r.height));
        });
        scr.querySelectorAll('.btn,.key').forEach(el=>{
          if (el.scrollWidth > el.clientWidth+1 || el.scrollHeight > el.clientHeight+1) report('button_overflow', sc, vid, l, label(el), el.scrollWidth+'x'+el.scrollHeight+' in '+el.clientWidth+'x'+el.clientHeight);
        });
        // 3. widgets inside the screen, touch regions of at least 40 in both directions
        scr.querySelectorAll('[data-w]').forEach(el=>{
          const r = rel(el);
          if (r[0] < 0 || r[1] < 0 || r[0]+r[2] > 272 || r[1]+r[3] > 480) report('out_of_screen', sc, vid, l, label(el), r.join(','));
          const name = el.dataset.w.replace(/^[^.]*\./,'');
          if (name.length > 14) longNames.add(el.dataset.w);
        });
        scr.querySelectorAll('.btn,.key,.hit,.rowhit').forEach(el=>{
          if (el.closest('.nav')) return;
          const r = rel(el);
          if (Math.min(r[2],r[3]) < 40) report('touch_small', sc, vid, l, label(el), r[2]+'x'+r[3]);
        });
      }
    });
  }
  // coverage: every page of project.json has a base screen, no screen draws a page that is not in the project, none twice
  const coverage = {
    pages: FW_PAGES.length,
    missing: FW_PAGES.filter(p=>!pages[p.key] && !(p.key in RETIRED_PAGES)).map(p=>p.id+' '+p.key),
    retired: Object.keys(RETIRED_PAGES).map(k=>FW_BY_NAME[k]+' '+k+': '+RETIRED_PAGES[k]),
    drawnRetired: Object.keys(RETIRED_PAGES).filter(k=>pages[k]),
    unknown: Object.keys(pages).filter(k=>!(k in FW_BY_NAME)),
    duplicate: Object.entries(pages).filter(([k,v])=>v.length>1).map(([k,v])=>k+': '+v.join(', '))
  };
  // slots: a value never changes the size or the place of its slots, and fits them
  CUR = 'stress';
  const stress = [];
  const slotsOf = html => { host.innerHTML = '<div class="scr">'+html+'</div>'; const b = host.getBoundingClientRect();
    return [...host.querySelectorAll('.vp')].map(e=>{ const r=e.getBoundingClientRect(), t=_range(e.querySelector('span')); return {name:e.dataset.w||'', rect:[Math.round(r.x-b.x),Math.round(r.y-b.y),Math.round(r.width),Math.round(r.height)], tw:t.width, text:e.textContent}; }); };
  const recipes = [
    ['heatValue big',   FIXTURES.temp.map(([c,t])=>heatValue(24,100,124,50,{cur:c,tar:t,on:true,name:'n',big:true})), [24,100,124,50]],
    ['heatValue print', FIXTURES.temp.map(([c,t])=>heatValue(56,100,110,58,{cur:c,tar:t,on:true,name:'n',big:false,mid:true})), [56,100,110,58]],
    ['heatValue cur only', FIXTURES.temp.map(([c])=>heatValue(60,100,112,52,{cur:c,on:false,name:'n',big:true})), [60,100,112,52]],
    ['pctValue tool',   FIXTURES.percent.map(v=>pctValue(56,100,104,30,v,'v')), [56,100,104,30]],
    ['pctValue fan',    FIXTURES.percent.map(v=>pctValue(188,100,60,40,v,'f',{align:'r'})), [188,100,60,40]],
    ['pctValue centre', FIXTURES.percent.map(v=>pctValue(96,100,80,28,v,'p',{align:'c'})), [96,100,80,28]],
    ['zoffValue',       FIXTURES.zoffset.map(v=>zoffValue(56,100,104,30,v,'z')), [56,100,104,30]],
    ['coordValue',      FIXTURES.coord.map(v=>coordValue(22,56,44,'X',v,'x_pos')), [22,56,74,44]],
    ['numberInput',     FIXTURES.input.map(v=>numberInput(56,v,'°C',350)), [24,56,224,72]]
  ];
  recipes.forEach(([name,variants,region])=>{
    const sets = variants.map(slotsOf), first = JSON.stringify(sets[0].map(s=>[s.name,s.rect]));
    sets.forEach((set,i)=>{
      if (JSON.stringify(set.map(s=>[s.name,s.rect])) !== first) stress.push({recipe:name, problem:'slots move', fixture:i});
      set.forEach(s=>{
        if (s.tw > s.rect[2]+0.5) stress.push({recipe:name, problem:'text wider than its slot', fixture:i, slot:s.name, text:s.text, width:Math.round(s.tw), slotWidth:s.rect[2]});
        if (s.rect[0] < region[0] || s.rect[0]+s.rect[2] > region[0]+region[2]+0.5) stress.push({recipe:name, problem:'slot outside its area', fixture:i, slot:s.name, rect:s.rect, area:region});
      });
    });
  });
  // names from the host are cut to their slot: at most the lines allowed, every line fits, the extension stays
  const names = ['Benchy_PLA_0.2mm.gcode','part_with_a_very_long_name.gcode','a.b.c.d.e.f.g.h.i.j.k.l.m.n.o.p.q.r.s.t.gcode','no extension but a very very long file name here','file name with spaces and a long tail.gcode','长长长长长长长长长长长长长长长长长长长长长长长长长长.gcode','שם_קובץ_ארוך_מאוד_מאוד_מאוד_מאוד_מאוד_מאוד.gcode','éééééééééééééééééééééééééééééé.gcode','.hidden-file-name-that-is-very-long-and-has-no-extension-at-all','x.gcode'];
  [[108,'t13',2],[248,'t16',1],[224,'t16',2],[216,'t19',1,{ext:false}],[184,'t16',1,{ext:false}]].forEach(([w,role,lines,o])=>{
    names.forEach(n=>{
      const out = fitName(n,w,role,lines,o);
      if (out.length > lines) stress.push({recipe:'fitName', problem:'too many lines', name:n, w:w, role:role});
      out.forEach(line=>{ if (textW(line,role) > w+0.5) stress.push({recipe:'fitName', problem:'line too wide', name:n, w:w, role:role, line:line}); });
      const dot = n.lastIndexOf('.'), ext = (!(o&&o.ext===false) && dot > 0 && n.length-dot <= 9) ? n.slice(dot) : '';
      if (ext && out.join('') !== n && !out[out.length-1].endsWith(ext)) stress.push({recipe:'fitName', problem:'extension lost', name:n, w:w, role:role, line:out[out.length-1]});
    });
  });
  host.remove();
  const problems = Object.values(found).map(p=>Object.assign(p,{langs:[...new Set(p.langs)].join(',')}));
  const result = {renders, coverage, problems, stress, longNames:[...longNames].sort(), fonts:[...ALLOWED]};
  const pre = document.createElement('pre'); pre.id='hwaudit'; pre.textContent = JSON.stringify(result); document.body.appendChild(pre);
}

// ?audit=names: the widget names the mockup uses, per stock page name (every variant, English): audit.py --names compares them with the widgets of the project
function namesAudit(){
  const host = document.createElement('div'); host.style.cssText='position:absolute;left:0;top:0'; document.body.appendChild(host);
  const out = {};
  for (const sc of SCREENS){
    const vids = sc.variants ? sc.variants.map(v=>v.id) : [''];
    vids.forEach(vid=>{
      host.innerHTML = renderScreen(sc,2,vid);
      const scr = host.querySelector('.scr'), old = scr.dataset.old, set = (out[old] = out[old] || {page:newPage(old), id:sc.id, widgets:[]});
      scr.querySelectorAll('[data-w]').forEach(el=>{ const w = el.dataset.w.replace(/^[^.]*\./,''); if (!set.widgets.includes(w)) set.widgets.push(w); });
    });
  }
  host.remove();
  const pre = document.createElement('pre'); pre.id = 'names'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
}

// ?audit=layout: every screen and variant (English) as data: the named widgets (rectangle, kind, font role, colours) for the generator of the screen project
// (tools/gen_project.py); export_layout.py writes layout.json
function layoutExport(){
  const host = document.createElement('div'); host.style.cssText='position:absolute;left:0;top:0;width:272px;height:480px'; document.body.appendChild(host);
  const out = [];
  const kindOf = el => ['t','btn','hit','rowhit','bar','thumb','anim','tab','key','card','nav','sw','radio','step'].find(c=>el.classList.contains(c)) || (el.tagName==='IMG'?'img':'box');
  for (const sc of SCREENS){
    const vids = sc.variants ? sc.variants.map(v=>v.id) : [''];
    vids.forEach(vid=>{
      host.innerHTML = renderScreen(sc,2,vid);
      const scr = host.querySelector('.scr'), r0 = scr.getBoundingClientRect(), widgets = [], prims = [];
      const rgb = c => { const m = c.match(/\d+(\.\d+)?/g).map(Number); return m[3] === 0 ? null : m.slice(0,3); };
      const matteAt = (el, r) => {      // the colour under the middle of an element: the first thing below it that is painted
        const stack = document.elementsFromPoint(r.left + r.width/2, r.top + r.height/2);
        for (let i = stack.indexOf(el) + 1; i < stack.length; i++){ const e = stack[i]; if (!scr.contains(e) || e === scr) break; if (el.contains(e)) continue; const c = rgb(getComputedStyle(e).backgroundColor); if (c) return c; }
        return [0x17,0x17,0x1a];
      };
      const order = Array.from(scr.querySelectorAll('*'));
      scr.querySelectorAll('*').forEach(el=>{
        if (el.closest('.grid-ov,.guide') || el.tagName === 'svg' || el.closest('svg')) return;
        const r = el.getBoundingClientRect(), cs = getComputedStyle(el); if (!r.width || !r.height) return;
        const box = {x: Math.round(r.left-r0.left), y: Math.round(r.top-r0.top), w: Math.round(r.width), h: Math.round(r.height)};
        if (el.classList.contains('ico')){ prims.push({...box, z: order.indexOf(el), prim: 'icon', icon: el.dataset.ico, sw: +el.dataset.sw, color: rgb(cs.color), matte: matteAt(el, r)}); return; }
        const bg = rgb(cs.backgroundColor);
        if (bg && !el.classList.contains('t')) prims.push({...box, z: order.indexOf(el), prim: 'fill', name: el.dataset.w ? el.dataset.w.replace(/^[^.]*\./,'') : null, bg, radius: parseFloat(cs.borderTopLeftRadius) || 0, matte: matteAt(el, r), cls: el.className});
      });
      scr.querySelectorAll('[data-w]').forEach(el=>{
        const r = el.getBoundingClientRect(), cs = getComputedStyle(el), kind = kindOf(el);
        const role = (el.className.match(/\br-(t13|t16|t19|d20|d28|d32)\b/)||[])[1] || null;
        const w = {z: order.indexOf(el), name: el.dataset.w.replace(/^[^.]*\./,''), kind, x: Math.round(r.left-r0.left), y: Math.round(r.top-r0.top), w: Math.round(r.width), h: Math.round(r.height)};
        if (role) w.role = role;
        if (kind==='t'){ w.align = el.classList.contains('c')?'c':el.classList.contains('r')?'r':'l'; w.color = rgb(cs.color); w.dyn = el.classList.contains('dyn'); w.text = el.textContent; w.matte = matteAt(el, r); w.top = el.classList.contains('top'); }
        const bg = rgb(cs.backgroundColor); if (bg) w.bg = bg;
        if (parseFloat(cs.borderTopLeftRadius)) w.radius = parseFloat(cs.borderTopLeftRadius);
        if (kind==='btn') w.label = el.textContent.trim();
        widgets.push(w);
      });
      out.push({id: sc.id, page: scr.dataset.page, old: scr.dataset.old, variant: vid, bg: [0x17,0x17,0x1a], widgets, prims});
    });
  }
  host.remove();
  const pre = document.createElement('pre'); pre.id = 'layout'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
}
function init(){
  const q = new URLSearchParams(location.search);
  if (q.has('lang')) lang = +q.get('lang');
  if (q.get('audit') === '1'){ document.getElementById('side').style.display='none'; spacingAudit(); return; }
  if (q.get('audit') === 'spec'){ document.getElementById('side').style.display='none'; document.fonts.ready.then(firmwareSpec); return; }
  if (q.get('audit') === 'layout'){ document.getElementById('side').style.display='none'; const run=()=>layoutExport(); if (document.fonts && document.fonts.ready) document.fonts.ready.then(run); else run(); return; }
  if (q.get('audit') === 'names'){ document.getElementById('side').style.display='none'; namesAudit(); return; }
  if (q.get('audit') === 'hw'){
    document.getElementById('side').style.display='none';
    const run = () => hwAudit();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(run); else run();
    return;
  }
  setInterval(()=>{            // the frames of the animations (the project's own pictures)
    const t = Date.now();
    document.querySelectorAll('img[data-anim]').forEach(im=>{
      const i = Math.floor(t/(+im.dataset.ms)) % (+im.dataset.n);
      if (im.dataset.cur !== String(i)){ im.dataset.cur = String(i); im.src = animSrc(im.dataset.anim,i); }
    });
  }, 100);
  const side = document.getElementById('side');
  const opts = LANG_NAMES.map((n,i)=>`<option value="${i}"${i===lang?' selected':''}>${n} (${LANGS[i]})</option>`).join('');
  side.innerHTML = `<h1>QIDI Q1 Pro screen — mockup</h1><p>272 × 480. Texts are the real ones of the project, in all 13 languages.</p>
   <label>Language</label><select id="lang">${opts}</select>
   <label>Size</label><div class="row"><button data-z="1" class="on">1×</button><button data-z="1.5">1.5×</button><button data-z="2">2×</button></div>
   <label>Overlays</label><div class="row"><button id="grid">8 px grid</button><button id="names">Widget names</button></div>
   <nav><b>Overview</b><a href="#tokens">Design tokens</a><a href="#components">Components</a>${GROUPS.map((g,i)=>`<b>${g}</b>`+SCREENS.filter(s=>s.group===g).map(s=>`<a href="#s-${s.id}">${s.title}</a>`).join('')).join('')}</nav>`;
  document.getElementById('lang').onchange = e=>{ lang=+e.target.value; render(); };
  side.querySelectorAll('[data-z]').forEach(b=>b.onclick=()=>{ zoom=+b.dataset.z; side.querySelectorAll('[data-z]').forEach(x=>x.classList.toggle('on',x===b)); render(); });
  document.getElementById('grid').onclick=e=>{ showGrid=!showGrid; e.target.classList.toggle('on',showGrid); render(); };
  document.getElementById('names').onclick=e=>{ showNames=!showNames; e.target.classList.toggle('on',showNames); render(); };
  if(q.has('zoom')) zoom=+q.get('zoom');
  if (q.has('bare')){      // one screen at 0,0, nothing around it (the static layer: ?static=1 hides what the screen draws at run time)
    side.style.display='none';
    const sc = findScreen(q.get('bare')); if (q.has('variant') && sc.variants) VSTATE[sc.id] = q.get('variant');
    const run = () => { document.body.style.cssText='margin:0;background:'+(q.has('onlybtn')?'transparent':'#181818'); document.documentElement.style.background=q.has('onlybtn')?'transparent':''; document.body.classList.toggle('static', q.has('static')); document.body.classList.toggle('nobtn', q.has('nobtn')); document.body.classList.toggle('onlybtn', q.has('onlybtn'));
      const m = document.getElementById('main'); m.style.cssText='padding:0;margin:0;position:absolute;left:0;top:0'; m.innerHTML = renderScreen(sc);
      if (q.has('hidebox')) {      // elements that lie inside one of these rectangles (x,y,w,h;...) are left out: pieces that are pictures of their own on the page (an icon on a card, the bar of the steps)
        const sc = m.querySelector('.scr'), o = sc.getBoundingClientRect(), boxes = q.get('hidebox').split(';').map(b => b.split(',').map(Number));
        sc.querySelectorAll('*').forEach(e => { const r = e.getBoundingClientRect(); if (!r.width || !r.height) return;
          const x = r.left - o.left, y = r.top - o.top;
          if (boxes.some(([bx, by, bw, bh]) => x >= bx - 2 && y >= by - 2 && x + r.width <= bx + bw + 2 && y + r.height <= by + bh + 2)) e.classList.add('hid'); }); }
      if (q.has('hide')) { const gone = new Set(q.get('hide').split(',')); m.querySelectorAll('[data-w]').forEach(e => { if (gone.has(e.dataset.w.split('.').pop())) e.classList.add('hid'); }); }
      if (q.has('lyr')) { const names = new Set(q.get('lyr').split(',')); m.querySelectorAll('[data-w]').forEach(e => { if (names.has(e.dataset.w.split('.').pop())) e.classList.add('lyr'); }); } };
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(run); else run();
    return;
  }
  if(q.has('only')){      // for screenshots: just these screens (?only=a,b&all=1 for every language, &variant=speed_mute for the variant of the screens that have it)
    side.style.display='none';
    const ids=q.get('only').split(',');
    let h='<div class="grid" style="padding:16px">';
    ids.forEach(id=>{ const sc=findScreen(id); if(!sc) return;
      if (q.has('variant') && sc.variants && sc.variants.some(v=>v.id===q.get('variant'))) VSTATE[sc.id] = q.get('variant');
      if(q.has('all')) h += langGrid(sc);
      else h+=cardHTML(sc,zoom); });
    document.getElementById('main').innerHTML=h+'</div>'; document.getElementById('main').style.padding='0';
    document.body.classList.toggle('showgrid', q.has('grid')); document.body.classList.toggle('show-names', q.has('names'));
    return;
  }
  render();
}
