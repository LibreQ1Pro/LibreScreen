// ---- the pieces of the design: every function returns HTML positioned on the 272 x 480 screen -----------------------
const LANGS = ['zh','ru','en','ja','fr','de','it','es','ko','pt','ar','tr','he'];
const LANG_NAMES = ['中文简体','Русский','English','日本語','Français','Deutsch','Italiano','Español','한국어','Português','العربية','Türkçe','עברית'];
let lang = 2;
let CUR = '';            // the screen that is being built (the key of its texts)
let VARIANT = '';        // the variant of the screen that is being built ('' = its first one)
const HOT = '#ff795a';   // a heater that is on

const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function anyText(key){ for(const p in TEXTS){ const e=TEXTS[p][key]; if(e && (e[lang]||e[2])) return e; } return null; }
// The line breaks inside the stock strings were made for the old widths (tools/english_copy.py computes them from the glyph widths of the
// component); the mockup lets the text flow in the widget it has now, so it joins the lines (without a space for Chinese and Japanese).
const soft = v => String(v).replace(/\n/g, (lang === 0 || lang === 3) ? '' : ' ');
function T(key, page, fb){
  const p = page || CUR;
  let e = (TEXTS[p] || {})[key];
  if(!e || !(e[lang]||e[2])) e = anyText(key) || e;
  let v = e && (e[lang] || e[2]);
  if (v == null || v === '') v = (fb != null ? fb : key);
  return esc(soft(v));
}
// the strict lookup for the texts a variant depends on: the key of this page only, the language, else the English text of the same page
function Tx(key, page){
  const e = (TEXTS[page || CUR] || {})[key];
  const v = e && (e[lang] || e[2]);
  return v == null ? '' : esc(soft(v));
}
function raw(key, page){ const e=(TEXTS[page||CUR]||{})[key]; return e && (e[lang]||e[2]) || ''; }
const isRtl = () => lang === 10 || lang === 12;
function ico(name, size, color, sw){
  const s = ICONS[name] || ICONS['image'];
  const w = sw || 2;
  return `<span class="ico" data-ico="${ICONS[name]?name:'image'}" data-sw="${w}" style="width:${size}px;height:${size}px;color:${color||'currentColor'}">${s.replace('stroke-width="2"','stroke-width="'+w+'"')}</span>`;
}
const st = (x,y,w,h,extra) => `left:${x}px;top:${y}px;width:${w}px;height:${h}px;${extra||''}`;
// The pages have readable names in the new design (pages.json: old name -> new name); the texts of the mockup are still keyed by the old names
// (CUR is the old name), everything that is shown (data-page, the names of the widgets, the tooltips, the gallery) uses the new one.
const newPage = old => PAGE_NAMES[old] || old;
function nm(name){ return name ? ` data-w="${newPage(CUR)}.${name}"` : ''; }
function tip(name,x,y,w,h){ return name ? newPage(CUR)+'.'+name+'  '+x+','+y+'  '+w+'×'+h : ''; }
function box(x,y,w,h,cls,inner,name,extra){ return `<div class="${cls||''}"${nm(name)} title="${tip(name,x,y,w,h)}" style="${st(x,y,w,h,extra)}">${inner||''}</div>`; }
function rect(x,y,w,h,color,r,extra){ return `<div style="${st(x,y,w,h)}background:${color};border-radius:${r||0}px;${extra||''}"></div>`; }

// ---- the six fonts of the screen ---------------------------------------------------------------------------------------
// One size and weight is one font resource (.zi): text 13 / 16 / 19 and digits 20 / 28 / 32. Nothing on a screen uses another size.
// The preview is Noto Sans, so the weights and the metrics are provisional until the real fonts are rendered.
const ROLES = {t13:{s:13,w:400}, t16:{s:16,w:500}, t19:{s:19,w:600}, d20:{s:20,w:600}, d28:{s:28,w:600}, d32:{s:32,w:600}};
const BASE_K = 0.388;    // baseline of a centred line = y + h/2 + BASE_K * size (Noto Sans; put the measured value of the .zi here)

// text: o = {a:'c'|'r', sz:'s'|'m'|'l'|'d' or role, mute, acc, red, v:'top'|'bottom', num, css}
const SZ_ROLE = {s:'t13', m:'t16', l:'t19', d:'d28'};
// Text that comes from the host (names of files and networks, messages of Klipper) can have any character, so the font it is drawn in has to be
// the wide one (the whole of Unicode that is needed: about 6 MB). The static texts only need the characters of the project's strings. Flash has room
// for one wide font, so every text of the host is drawn in ONE role (class "dyn"); the audit checks it.
const DYNAMIC_ROLE = 't16';
function txt(x,y,w,h,content,o,name){
  o = o || {};
  const role = o.role || SZ_ROLE[o.sz||'m'];
  const cls = ['t', o.a==='c'?'c':'', o.a==='r'?'r':'', 'r-'+role, o.mute?'mute':'', o.acc?'acc':'', o.red?'red':'', o.v==='top'?'top':'', o.v==='bottom'?'bottom':'', o.nowrap?'nw':'', o.dyn?'dyn':'', isRtl()&&!o.num?'rtl':''].join(' ');
  return `<div class="${cls}"${nm(name)} title="${tip(name,x,y,w,h)}" style="${st(x,y,w,h,o.css)}"><span>${content}</span></div>`;
}
const tt = (x,y,w,h,key,o,name) => txt(x,y,w,h,T(key),o,name||key);   // a text widget of the page

// ---- fixed slots: a value with its unit ("35 %", "220 / 250 °C") -------------------------------------------------------------
// A text widget draws one font and cannot change its width at run time (x and y can, w and h cannot): "35 %" is two widgets, a number
// and a unit. Each slot has a width that is a constant of the layout, wide enough for the longest value; the number is aligned to the
// right and the unit to the left, so the seam between them never moves. Nothing here looks at the text.
function slot(x,y,w,h,text,role,o){
  o = o || {};
  const cls = ['t','vp', o.a==='r'?'r':o.a==='c'?'c':'', 'r-'+role].join(' ');
  return `<div class="${cls}"${nm(o.name)} title="${tip(o.name,x,y,w,h)}" style="${st(x,y,w,h)}${o.color?';color:'+o.color:''}"><span style="white-space:nowrap">${o.raw?text:esc(text)}</span></div>`;
}
// parts: [{t, role, w, a:'l'|'r'|'c', color, name}]; y,h: the box of the first part, the others sit on its baseline.
// o.align: 'l' (start at x), 'c' or 'r' = the group (its constant width) is centred / right-aligned in x..x+w
function run(x,y,w,h,parts,o){
  o = o || {};
  const gap = o.gap == null ? 3 : o.gap;
  const total = parts.reduce((s,p)=>s+p.w,0) + gap*(parts.length-1);
  let cx = o.align==='r' ? x+w-total : o.align==='c' ? x+Math.round((w-total)/2) : x;
  const base = y + h/2 + BASE_K*ROLES[parts[0].role].s;
  return parts.map(p=>{
    const s = ROLES[p.role].s, ph = Math.ceil(s*1.4/2)*2, py = Math.round(base - ph/2 - BASE_K*s);
    const out = slot(cx,py,p.w,ph,p.t,p.role,{a:p.a,color:p.color,name:p.name,raw:p.raw});
    cx += p.w + gap; return out;
  }).join('');
}
// the value of a widget the host has not set yet: "---" (the digit fonts have the character "-"); the state "no values" of a screen shows it
const dv = x => isV('no_values') ? '---' : x;
const lit = on => isV('heat_on') ? true : isV('heat_off') ? false : (on && !isV('no_values'));   // the variants heat_on / heat_off: every heater lit / not (the icons of the screens)      // a heater whose state is not known yet is not drawn as heating
// the recipes: current / target temperature with the unit. The current temperature is always digits 28 (home, filament, print);
// big = the target is text 16 too (room for 124), else text 13 (the print rows have 110); big:false without mid = digits 20 (not used on a page)
function heatValue(x,y,w,h,v){
  const big = v.big !== false, d28 = big || v.mid;     // mid: digits 28 with the small target (the print rows, 110 wide)
  const parts = [{t:String(dv(v.cur)), role:d28?'d28':'d20', w:d28?52:36, a:'r', color:lit(v.on)?HOT:'var(--text)', name:v.name+'_temp'}];
  if (v.tar != null) parts.push({t:'/ '+dv(v.tar), role:big?'t16':'t13', w:big?44:34, a:'l', color:'var(--text3)', name:v.name+'_set'});
  parts.push({t:'°C', role:'t13', w:big?20:18, a:'l', color:'var(--text2)', name:v.name+'_unit'});
  return run(x,y,w,h,parts,{gap:3,align:v.align||'l'});
}
// a percentage: digits 20 and "%" (up to three digits)
function pctValue(x,y,w,h,val,name,o){
  o = o || {};
  return run(x,y,w,h,[{t:String(dv(val)), role:o.role||'d20', w:o.nw||40, a:'r', name:name}, {t:'%', role:'t13', w:16, a:'l', color:'var(--text2)', name:name+'_u'}],{align:o.align||'l',gap:3});
}
// the Z offset: a sign, up to two digits, three decimals ("-99.999") and "mm"
function zoffValue(x,y,w,h,val,name,o){
  o = o || {};
  return run(x,y,w,h,[{t:String(dv(val)), role:'d20', w:76, a:'r', name:name}, {t:'mm', role:'t13', w:24, a:'l', color:'var(--text2)', name:name+'_u'}],{gap:3,align:o.align||'l'});
}
// a coordinate of the move page: the axis and the position ("-999.99")
function coordValue(x,y,h,axis,val,name){
  return run(x,y,74,h,[{t:axis, role:'t16', w:12, a:'l', color:'var(--text2)'}, {t:String(dv(val)), role:'t16', w:60, a:'l', name:name}],{gap:2});
}
// the input field of the number keyboards: digits 32 and the unit; "MAX" is a caption under the digits (only on the full field)
function numberInput(y,value,unit,max){
  const full = max != null;
  return card(12,y,248,full?72:44,'background:#101010') +
    run(24,y+(full?4:0),224,44,[{t:String(value), role:'d32', w:70, a:'r', name:'input_show'}, {t:unit, role:'t16', w:30, a:'l', color:'var(--text2)', name:'input_unit'}],{align:'r',gap:3}) +
    (full ? slot(24,y+46,224,22,'MAX : '+max,'t13',{color:'var(--text2)',name:'input_max'}) : '');
}

// ---- long texts: the host cuts a name to its slot (two lines, the extension stays) ---------------------------------------
const _cv = document.createElement('canvas').getContext('2d');
function textW(t,role){ const r = ROLES[role]; _cv.font = `${r.w} ${r.s}px 'Noto Sans'`; return _cv.measureText(t).width; }
const _seg = (typeof Intl !== 'undefined' && Intl.Segmenter) ? new Intl.Segmenter(undefined,{granularity:'grapheme'}) : null;
const graphemes = s => _seg ? Array.from(_seg.segment(s), x=>x.segment) : Array.from(s);
// name -> the lines that fit maxW (at most maxLines): the last line ends with "…" + the extension. o.ext=false: no extension (a SSID).
function fitName(name,maxW,role,maxLines,o){
  o = o || {};
  if (textW(name,role) <= maxW) return [name];
  const g = graphemes(name), lines = [];
  let rest = g;
  for (let li=0; li<maxLines-1; li++){
    let n = 0;
    while (n < rest.length && textW(rest.slice(0,n+1).join(''),role) <= maxW) n++;
    if (n === 0) n = 1;
    if (n < rest.length) {      // break where a name can be broken: after _ - space, before the dot of the extension
      for (let b = n; b >= Math.ceil(n*0.4); b--) {
        if (b < rest.length && (rest[b] === '.' || ['_','-',' '].includes(rest[b-1]))) { n = b; break; }
      }
    }
    lines.push(rest.slice(0,n).join('')); rest = rest.slice(n);
    if (!rest.length) return lines;
  }
  const tail = rest.join('');
  if (textW(tail,role) <= maxW){ lines.push(tail); return lines; }
  const dot = name.lastIndexOf('.');
  let ext = (o.ext !== false && dot > 0 && name.length-dot <= 9) ? name.slice(dot) : '';
  let stem = tail;
  if (ext && tail.endsWith(ext)) stem = tail.slice(0,-ext.length); else ext = '';
  if (textW('…'+ext,role) > maxW) ext = '';
  const sg = graphemes(stem);
  while (sg.length && textW(sg.join('')+'…'+ext,role) > maxW) sg.pop();
  lines.push(sg.join('')+'…'+ext);
  return lines;
}
const nameHTML = (name,maxW,role,maxLines,o) => fitName(name,maxW,role,maxLines,o).map(esc).join('<br>');
// a name in a fixed box, cut by fitName
function nameBox(x,y,w,h,name,role,maxLines,o,wname){
  o = o || {};
  return txt(x,y,w,h,nameHTML(name,w,role,maxLines,o),{role:role,a:o.a,v:o.v,num:1,css:o.css,nowrap:1,dyn:1},wname);
}
// a text area that scrolls (an error message of any length): the thumb of the scroll bar shows that there is more
function scrollBox(x,y,w,h,html,o,name){
  o = o || {};
  return `<div class="t scroll top dyn r-${o.role||'t16'}"${nm(name)} title="${tip(name,x,y,w,h)}" style="${st(x,y,w,h,o.css)}"><span style="padding-right:${o.bar===false?0:8}px">${html}</span></div>` +
    (o.bar === false ? '' : rect(x+w-4,y,3,h,'#313039',2) + rect(x+w-4,y,3,Math.round(h*0.5),'var(--text3)',2));
}

// ---- touch regions ---------------------------------------------------------------------------------------------------------------
// A touch region is a widget of its own (a button with no picture): the decorative parts of a control never are the target.
function hit(x,y,w,h,name){ return `<div class="hit"${nm(name)} title="${tip(name,x,y,w,h)}" style="${st(x,y,w,h)}"></div>`; }
// a slider: a track of 10 px and a knob of 28 px inside a touch region of 44; the knob stays inside the region at both ends
function slider(x,y,w,val,name,o){
  o = o || {};
  const lo = o.min == null ? 0 : o.min, hi = o.max == null ? 100 : o.max, frac = (val-lo)/(hi-lo || 1);
  const th = 44, tr = 10, kn = 28, tx = x+kn/2, tw = w-kn, kx = Math.round(tx+tw*frac), cy = y+th/2;
  let s = hit(x,y,w,th,name);
  s += box(tx,cy-tr/2,tw,tr,'bar','<i style="width:'+Math.round(100*frac)+'%"></i>');
  (o.ticks||[]).forEach(v=>{ s += rect(Math.round(tx+tw*(v-lo)/(hi-lo))-1,cy+tr/2+3,2,6,'#4a4952',1); });
  s += `<div style="${st(kx-kn/2,cy-kn/2,kn,kn)}background:#fff;border-radius:${kn/2}px"></div>`;
  return s;
}

// ---- the animations of the project: the real frames, played in the gallery -------------------------------------------------------
const animSrc = (key,i) => (ANIMS[key].dir || '../animations/') + key + '/' + String(i).padStart(3,'0') + '.png';
function animImg(key,x,y){
  const a = ANIMS[key];
  return `<img data-anim="${key}" data-n="${a.n}" data-ms="${a.ms}" src="${animSrc(key,0)}" alt="" style="${st(x,y,a.w,a.h)}">`;
}
// a block of the page that plays an animation: the frames keep their own size and sit in the middle of the block, so a frame that is
// larger than the block is cropped and a smaller one leaves the background of the block visible
function animBlock(x,y,w,h,key,name){
  const a = ANIMS[key];
  return `<div class="anim"${nm(name)} title="${tip(name,x,y,w,h)}${name?'  frame '+a.w+'×'+a.h:''}" style="${st(x,y,w,h,'overflow:hidden')}">${animImg(key,Math.round((w-a.w)/2),Math.round((h-a.h)/2))}</div>`;
}
// ---- the steps of a wizard (setup guide, filament load / unload, auto leveling) ---------------------------------------------------------
// A list of steps: a circle (done = green with a check, active = blue, the others grey; static pictures, nothing blinks), a line to
// the next one and a text slot per step. items: [{y, h, html, name}] (y = top of the circle, the text is top-aligned from y + 2).
function wizSteps(items, active){
  let s = '';
  items.forEach((p,i)=>{
    const done = i < active, on = i === active;
    s += `<div class="step${done?' done':on?' on':''}" style="${st(14,p.y-1,26,26)}">${done?ico('check',16,'#fff',3):i+1}</div>`;
    if (i < items.length-1) s += `<div class="vline" style="${st(26,p.y+28,2,items[i+1].y-p.y-32)}"></div>`;
    s += txt(50,p.y+2,210,p.h,p.html,{v:'top',mute:!on},p.name);
  });
  return s;
}
// buttons
function btn(x,y,w,h,label,o,name){
  o = o || {};
  const cls = ['btn', o.v||'', o.press?'press':'', o.wrap?'wrap':'', o.col?'col':''].join(' ');
  const inner = (o.icon?(o.left?`<div style="position:absolute;left:16px;top:${(h-(o.is||22))/2}px">${ico(o.icon,o.is||22,o.ic)}</div>`:ico(o.icon,o.is||22,o.ic)):'') + (label?(o.left?`<span${isRtl()?' class="rtl"':''} style="position:absolute;left:48px;right:10px;top:0;height:100%;display:flex;align-items:center;justify-content:${isRtl()?'flex-end':'flex-start'};text-align:${isRtl()?'right':'left'}">${label}</span>`:`<span${isRtl()?' class="rtl"':''} style="padding:0 ${o.wrap?3:6}px">${label}</span>`):'');
  return `<div class="${cls}"${nm(name)} title="${tip(name,x,y,w,h)}" style="${st(x,y,w,h,o.css)}">${inner}</div>`;
}
const tb = (x,y,w,h,key,o,name) => btn(x,y,w,h,T(key),o,name||key);
function row(x,y,w,h,label,o,name){          // a list row: label on the left, something on the right
  o = o || {};
  let right = '';
  if (o.chev) right = `<div style="${st(w-34,(h-22)/2,22,22)}color:var(--text3)">${ico('chevron-right',22)}</div>`;
  if (o.sw!=null) right = `<div class="sw${o.sw?' on':''}" style="left:${w-56}px;top:${(h-26)/2}px"></div>`;
  if (o.check) right = `<div style="${st(w-38,(h-24)/2,24,24)}color:var(--accent)">${ico('check',24,null,2.5)}</div>`;
  if (o.lock) right = `<div style="${st(w-36,(h-20)/2,20,20)}color:var(--text2)">${ico('lock',20)}</div>`;
  if (o.radio!=null) right = `<div class="radio${o.radio?' on':''}" style="left:14px;top:${(h-22)/2}px"></div>`;
  const left = o.radio!=null ? 46 : 16;
  const lw = w-left-(o.radio!=null?12:46);
  // a label that comes from the host (a SSID) is cut to its slot; a text of the project is written to fit
  const lab = o.cut ? txt(left,0,lw,h,nameHTML(label,lw,'t16',1,{ext:false}),{num:1,nowrap:1,dyn:1},null) : txt(left,0,lw,h,label.replace(/<br>/g,' '),{num:o.num},null);
  const bg = `<div style="${st(0,0,w,h)}background:${o.sel?'var(--btn-hi)':'var(--btn)'};border-radius:12px;${o.press?'opacity:.8':''}"></div>`;
  return `<div class="rowhit"${nm(name)} title="${tip(name,x,y,w,h)}" style="${st(x,y,w,h)}">${bg}${lab}${right}</div>`;
}
const toggle = (x,y,on) => `<div class="sw${on?' on':''}" style="left:${x}px;top:${y}px"></div>`;
function progress(x,y,w,h,pct,name){ return box(x,y,w,h,'bar',`<i style="width:${pct}%"></i>`,name); }
// A thumbnail is a picture the host has prepared for the widget: exactly its size, with the corners and the matte of the card already in
// the pixels (ColPic / JPEG have no alpha); the screen only shows it.
function thumb(x,y,w,h,name,glyph){ return box(x,y,w,h,'thumb',ico(glyph||'image',Math.min(w,h)*0.38,null,1.6),name); }
// chrome
const NAVS = [['house','main'],['sliders-horizontal','adjust'],['folder-open','files'],['settings','settings']];
function nav(active){
  let s='';
  NAVS.forEach((n,i)=>{ s+=`<div class="it${n[1]===active?' on':''}"${nm('nav_'+n[1])} style="left:${68*i}px"><div class="pill">${ico(n[0],22,null,2)}</div></div>`; });
  return `<div class="nav" style="${st(0,424,272,56)}">${s}</div>`;
}
function header(title, o){
  o = o || {};
  const back = btn(0,0,272,48,'',{icon:'chevron-left',is:26,css:'background:transparent;justify-content:flex-start;padding-left:11px;border-radius:0'},'back_btn');
  const right = o.right || '';
  return back + txt(48,0,o.tw||212,48,title,{role:o.role||'t19'},'title') + right + rect(0,48,272,1,'var(--line)');
}
// tabs: a segmented control; each half is a touch region of 124 x 40
function tabs(l,r,active,names){
  const n = names || ['tab_calib','tab_settings'];
  return `<div class="tabs" style="${st(12,8,248,40)}">`+
    `<div class="tab${active==='l'?' on':''}" style="${st(3,3,121,34)}">${T(n[0])}</div>`+
    `<div class="tab${active==='r'?' on':''}" style="${st(124,3,121,34)}">${T(n[1])}</div>`+
    hit(0,0,124,40,n[0]) + hit(124,0,124,40,n[1]) + `</div>`;
}
const card = (x,y,w,h,extra) => `<div class="card" style="${st(x,y,w,h,extra)}"></div>`;
function screen(page, body, o){
  o = o || {};
  CUR = page;
  return `<div class="scr" data-page="${newPage(page)}" data-old="${page}">${body}<div class="grid-ov"></div><div class="guide" style="${st(12,0,248,480)}"></div></div>`;
}
// heater icons (Lucide has no nozzle / bed / chamber): drawn here
const HEAT = {
  nozzle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="3" width="12" height="8" rx="2"/><path d="M9 11v3l3 6 3-6v-3"/></svg>',
  bed: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18h18"/><path d="M7 14c-1.5-1.5 1.5-2.500 0-4M12 14c-1.5-1.5 1.500-2.500 0-4M17 14c-1.500-1.500 1.500-2.500 0-4"/><path d="M3 21h18"/></svg>',
  flow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 2h10v5l-3 3h-4L7 7z"/><path d="M12 10v5"/><path d="m9.5 13 2.5 3 2.5-3"/><path d="M4 21h16"/></svg>',
  chamber: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v15"/><path d="M3 21h18"/><path d="M9 17c-1-1.5 1-2.5 0-4s1-2.5 0-4M15 17c-1-1.5 1-2.5 0-4s1-2.5 0-4"/></svg>'
};
function hico(name,size,color){ return `<span class="ico" data-ico="heat-${name}" data-sw="2" style="width:${size}px;height:${size}px;color:${color||'currentColor'}">${HEAT[name]}</span>`; }
