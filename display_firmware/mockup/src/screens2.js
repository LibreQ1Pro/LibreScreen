// ---- screens: filament, fans, move, calibration ---------------------------------------------------------------------
// a segmented control: each cell is a touch region of its own (the tall touch area is the cell, not the inner pill)
function seg(x,y,w,h,labels,active,names){
  const n = labels.length, cw = (w-6)/n, hw = w/n;
  return `<div class="tabs" style="${st(x,y,w,h)}">` +
    labels.map((l,i)=>`<div class="tab${i===active?' on':''}" style="${st(3+cw*i,3,cw,h-6)}">${l}</div>`).join('') +
    labels.map((l,i)=>hit(hw*i,0,hw,h,names&&names[i])).join('') + '</div>';
}
// a heater with its controls: one card like the heater rows of the print page (icon inside, current / target / unit); two touch regions on it:
// the icon switches the heater (orange = heating), the rest opens the keyboard for the target
function heatEdit(x,y,w,glyph,cur,tar,on,name,o){
  o = o || {};
  return box(x,y,w,50,'card hi','',name+'_card') +
    `<div style="${st(x+12,y+12,26,26)}color:${lit(on)?HOT:'var(--text2)'}">${hico(glyph,26)}</div>` +
    heatValue(x+44,y,w-50,50,{cur:cur,tar:tar,on:on,name:name,big:false,mid:true}) +
    (o.whole ? hit(x,y,w,50,name+'_toggle') : hit(x,y,50,50,name+'_toggle') + hit(x+50,y,w-50,50,name+'_row'));
}
S('filament','Filament and movement','Filament',()=>{
  CUR='filament';
  let s = tabs('l','r','l',['tab_load','tab_manual']);
  s += heatEdit(12,56,160,'nozzle',220,220,true,'nozzle')+heatEdit(12,114,160,'bed',60,60,true,'bed')+heatEdit(12,172,160,'chamber',35,0,false,'chamber');
  // the fans, as on the print page: three tiles (icon, number, speed); a tap opens the fans page
  s += [100,0,60].map((v,i)=>fanTile(180,56+58*i,80,50,i+1,v,'fan'+(i+1)+'_btn')).join('');
  s += tb(12,230,120,46,'load_btn',{},'load_btn')+tb(140,230,120,46,'replace_btn',{wrap:1},'replace_btn');
  const segA = {seg10:0, seg50:1, seg100:2}[VARIANT]; s += seg(12,284,248,40,['10 mm','50 mm','100 mm'],segA == null ? 1 : segA,['step_10','step_50','step_100']);
  s += btn(12,332,120,64,esc(caption('retract')),{icon:'arrow-up',is:24,col:1},'extr_up')+btn(140,332,120,64,esc(caption('extrude')),{icon:'arrow-down',is:24,col:1},'extr_down');
  s += nav('adjust');
  return screen('filament', s);
}, 'A heater is one card, as on the print page: tap the icon to switch it on or off (orange = heating), tap the value to set the temperature. The fans are three tiles, as on the print page; a tap opens the number keyboard for that fan (there is no separate fans page any more).',
 {variants:[{id:'normal',label:'Values'},{id:'no_values',label:'No values yet (---)'},{id:'heat_on',label:'All heaters on'},{id:'heat_off',label:'All heaters off'},{id:'seg10',label:'10 mm'},{id:'seg50',label:'50 mm'},{id:'seg100',label:'100 mm'}]});

S('move','Filament and movement','Move',()=>{
  CUR='move';
  let s = tabs('l','r','r',['tab_load','tab_manual']);
  s += card(12,56,248,44,'');
  ['X','Y','Z'].forEach((a,i)=>{ s += coordValue(22+76*i,56,44,a,'0.00',a.toLowerCase()+'_pos'); });
  const dA = {seg01:0, seg1:1, seg10:2}[VARIANT]; s += seg(12,108,248,40,['0.1 mm','1 mm','10 mm'],dA == null ? 1 : dA,['dist_01','dist_1','dist_10']);
  // control: a ring of 120 behind the cross, keys of 52 that are 8 apart, the Z keys at its right (8 away)
  s += `<div style="${st(46,190,120,120)}background:var(--panel);border-radius:60px"></div>`;
  s += btn(80,164,52,52,'',{icon:'chevron-up',is:28},'y_up')+btn(20,224,52,52,'',{icon:'chevron-left',is:28},'x_down')+btn(140,224,52,52,'',{icon:'chevron-right',is:28},'x_up')+btn(80,284,52,52,'',{icon:'chevron-down',is:28},'y_down');
  s += btn(80,224,52,52,'',{icon:'house',is:24,css:'border-radius:26px;background:var(--btn-hi)'},'home_btn');
  s += btn(208,156,52,90,'',{icon:'chevrons-up',is:28},'z_up')+btn(208,254,52,90,'',{icon:'chevrons-down',is:28},'z_down');
  s += btn(12,352,248,44,esc(caption('motors')),{icon:'power',is:22,left:1},'motors_off');
  s += nav('adjust');
  return screen('move', s);
}, 'Each position is a fixed slot of 60 px (up to "-999.99"); the values never change the size of a widget.',
 {variants:[{id:'normal',label:'Values'},{id:'no_values',label:'No values yet (---)'},{id:'seg01',label:'0.1 mm'},{id:'seg1',label:'1 mm'},{id:'seg10',label:'10 mm'}]});

// the number keyboard of the pages without a print status: the three temperatures (sys1 of the stock page filament_kb; MAX is the limit written on its
// picture) and the three fans (the modes of the print keyboard keybdB; a speed in %, 0..100), opened from the fan tiles. The title comes from the page the mode belongs to.
const KEYPAD = [
  {id:'nozzle',  label:'Nozzle',  title:['title@sys1=0','filament_kb'], unit:'°C', max:350, val:'220'},
  {id:'bed',     label:'Bed',     title:['title@sys1=1','filament_kb'], unit:'°C', max:120, val:'60'},
  {id:'chamber', label:'Chamber', title:['title@sys1=2','filament_kb'], unit:'°C', max:60,  val:'35'},
  {id:'fan1',    label:'Fan 1',   title:['title@sys0=4','keybdB'],      unit:'%',  max:100, val:'100'},
  {id:'fan2',    label:'Fan 2',   title:['title@sys0=5','keybdB'],      unit:'%',  max:100, val:'60'},
  {id:'fan3',    label:'Fan 3',   title:['title@sys0=6','keybdB'],      unit:'%',  max:100, val:'0'}
];
S('keypad','Filament and movement','Number keyboard',()=>{
  const m = KEYPAD.find(x=>x.id===(VARIANT||KEYPAD[0].id)) || KEYPAD[0];
  CUR='filament_kb';
  let s = header(Tx(m.title[0],m.title[1]),{role:'t16',tw:212});     // like the title of the print keyboard (the mode names are long)
  s += numberInput(56,m.val,m.unit,m.max);
  ['1','2','3','4','5','6','7','8','9','del','0','ok'].forEach((k,i)=>{
    const c=i%3,r=Math.floor(i/3); const fn=(k==='del');
    s += `<div class="key${fn?' fn':''}"${nm('key_'+k)} title="${tip('key_'+k,[12,97,183][c],136+66*r,[77,78,77][c],58)}" style="${st([12,97,183][c],136+66*r,[77,78,77][c],58)}${k==='ok'?';background:var(--accent)':''}">${k==='del'?ico('delete',24):k==='ok'?ico('check',28,'#fff',2.5):k}</div>`;
  });
  s += nav('adjust');
  return screen('filament_kb', s);
}, 'The modes of one page: the three temperatures (nozzle, bed, chamber) and the three fans (opened from the fan tiles of the filament page, a speed in %). The limit under the digits is the one written on the stock picture; the stock page does not clamp the value.',
 {variants:KEYPAD.map(m=>({id:m.id,label:m.label}))});

// -- calibration
S('calibration_menu','Calibration','Calibration menu',()=>{
  CUR='level_mode';
  let s = tabs('l','r','l',['tab_calib','tab_settings']);
  // a warning: the card with the warning icon (the same icon and tint as the warning pop-ups) and the message
  s += card(12,58,248,148,'') + `<div style="${st(112,68,48,48)}border-radius:24px;background:color-mix(in srgb, var(--warn) 18%, transparent);color:var(--warn);display:flex;align-items:center;justify-content:center">${ico('triangle-alert',26)}</div>`;
  s += tt(24,124,224,74,'msg',{a:'c'},'msg');
  s += row(12,214,248,50,T('auto_level'),{chev:1},'auto_level')+row(12,272,248,50,T('shaping'),{chev:1},'shaping')+row(12,330,248,50,T('bed_calib'),{chev:1},'bed_calib');
  s += nav('settings');
  return screen('level_mode', s);
});

function wizardFrame(page, title){ CUR=page; return txt(16,8,240,32,title,{role:'t19'},'title'); }
// auto leveling: four steps with an equal pitch (115, as in the stock page); the temperature of the bed is the line at the bottom
const AUTO_STEPS = [{id:'step1',label:'Step 1'},{id:'step2',label:'Step 2 (heating)'},{id:'step3',label:'Step 3'},{id:'step4',label:'Step 4'}];
S('auto_level_progress','Calibration','Auto leveling in progress',()=>{
  CUR='auto_moving';
  const active = Math.max(0,AUTO_STEPS.findIndex(x=>x.id===VARIANT));
  const items=[20,135,250,365].map((y,i)=>({y:y,h:i===3?64:96,html:T('step'+(i+1)+'_txt'),name:'step'+(i+1)+'_txt'}));
  let s = wizSteps(items,active);
  // the temperature of the bed is under the text of the heating step, like the temperature on the unload page
  s += `<div style="${st(50,182,18,18)}color:var(--text2)">${hico('bed',18)}</div>` + heatValue(74,177,186,28,{cur:'120',tar:'120',on:false,name:'bed',big:false});
  return screen('auto_moving', s);
}, 'Four steps, one list with an equal pitch (the stock page has the same); the active one is blue, the done ones have a check. The bed temperature is under the text of the heating step (the stock page has it as a line at the bottom).',
 {variants:AUTO_STEPS.map(x=>({id:x.id,label:x.label}))});
S('auto_level_preheat','Calibration','Preheat the bed',()=>{
  CUR='auto_heaterbed';
  let s = header('');
  s += heatEdit(12,56,248,'bed',120,120,true,'heat',{whole:true});
  s += btn(12,114,120,46,'',{icon:'minus',is:26},'temp_down')+btn(140,114,120,46,'',{icon:'plus',is:26},'temp_up');
  s += tt(16,176,240,230,'msg',{a:'c',mute:1},'msg');
  s += btn(12,420,248,46,'',{icon:'chevron-right',is:28,v:'primary'},'next_btn');
  return screen('auto_heaterbed', s);
}, '', {variants:[{id:'on',label:'Heating'},{id:'heat_on',label:'Heater on'},{id:'heat_off',label:'Heater off'}]});
// the pictures of the platform calibration pages (line art, made by tools/make_animations.py from the finished pictures: transparent,
// no frame; mockup/art/): each is exactly the size of its block, one pixel of the picture is one pixel of the screen; the card behind it is
// the page's background, the picture's lines run to its edge
const artPic = (file,x,y,w,h,name) => `<div class="art"${nm(name)} title="${tip(name,x,y,w,h)}" style="${st(x,y,w,h,'overflow:hidden;border-radius:14px;background:var(--card)')}"><img src="art/${file}.png" alt="" style="${st(0,0,w,h)}"></div>`;
S('reference_point','Calibration','Adjust the reference point',()=>{
  CUR='pre_bed_cal';
  let s = artPic('pre_bed_cal',12,12,248,80,'art');
  const dist = {d001:0, d005:1, d01:2, d05:3}[VARIANT || 'd005'];
  ['0.01','0.05','0.1','0.5'].forEach((v,i)=>{ s += `<div class="btn${i===dist?' primary':''}"${nm('cstep_'+v.replace('.',''))} title="${tip('cstep_'+v.replace('.',''),12+64*i,100,56,46)}" style="${st(12+64*i,100,56,46)}">${v}</div>`; });
  s += btn(12,154,120,46,'',{icon:'chevron-up',is:26},'z_up')+btn(140,154,120,46,'',{icon:'chevron-down',is:26},'z_down');
  s += tt(12,204,248,70,'title',{a:'c',acc:1,role:'t19'},'title')+tt(16,274,240,142,'msg',{a:'c',mute:1},'msg');
  s += btn(12,420,248,46,'',{icon:'chevron-right',is:28,v:'primary'},'enter_btn');
  return screen('pre_bed_cal', s);
}, 'The picture at the top is 248 x 80 (the platform with the feeler gauge), hand-finished line art (tools/make_animations.py), transparent over the card.',
 {variants:[{id:'d001',label:'0.01'},{id:'d005',label:'0.05'},{id:'d01',label:'0.1'},{id:'d05',label:'0.5'}]});
S('nut_adjust','Calibration','Nut adjusting',()=>{
  CUR='bed_calibrate';
  // two pictures of 116 x 140: the nut turned up and turned down (the stock background draws them)
  let s = artPic('bed_calibrate_up',12,12,120,140,'art_up') + artPic('bed_calibrate_down',140,12,120,140,'art_down');
  s += tt(12,160,248,32,'step_txt',{a:'c',acc:1,role:'t19'},'step_txt')+tt(16,200,240,210,'msg',{a:'c',mute:1},'msg');
  s += btn(12,420,248,46,'',{icon:'chevron-right',is:28,v:'primary'},'next_btn');
  return screen('bed_calibrate', s);
}, 'Two pictures of 120 x 140 side by side (the nut turned up and down), hand-finished line art (tools/make_animations.py).');
S('nut_choose','Calibration','Choose a nut',()=>{
  CUR='bed_finish';
  // a plain panel of 236 x 140 with the three nuts as buttons: there is no picture in it
  let s = box(18,12,236,140,'card','','panel');
  s += btn(86,24,100,48,T('screw3'),{},'screw3')+btn(30,88,100,48,T('screw1'),{},'screw1')+btn(142,88,100,48,T('screw2'),{},'screw2');
  s += tt(16,164,240,240,'msg',{a:'c',mute:1},'msg');
  s += tb(12,420,248,46,'ok',{v:'primary'},'ok');
  return screen('bed_finish', s);
}, 'No picture here: the panel only holds the three nut buttons (the labels are the stock texts, translated).');
S('z_offset_table','Calibration','Z offset table',()=>{
  CUR='zoffset';
  let s = header('');
  // two tables of the mesh (3 + 2 columns, a header and 5 rows); a cell is a text widget (the host sets the value), a header is a translated text
  const table=(y,cols,first)=>{ let h=''; const cw=Math.floor(248/cols);
    for(let r=0;r<6;r++) for(let c=0;c<cols;c++){ const head=r===0, col=first+c, x=12+cw*c, yy=y+30*r;
      const rad = r===0&&c===0?'8px 0 0 0':r===0&&c===cols-1?'0 8px 0 0':r===5&&c===0?'0 0 0 8px':r===5&&c===cols-1?'0 0 8px 0':'0';
      h += `<div style="${st(x,yy,cw,30)}background:${head?'#313039':r%2?'var(--panel)':'#212021'};border-radius:${rad}"></div>`;
      h += txt(x,yy,cw,30,head?T('cell_'+(25+col)):'0.000',{role:'t13',a:'c',num:1,mute:head,css:head?'':'color:var(--text)'},'cell_'+(head?25+col:5*(r-1)+col)); }
    return h; };
  s += table(60,3,0)+table(260,2,3);
  return screen('zoffset', s);
}, 'Two tables of the mesh: 3 + 2 columns, 5 rows. Header cells are the stock texts; the cells are text widgets (cell_0 ... cell_24, the headers cell_25 ... cell_29).');
S('auto_level_done','Calibration','Calibration done',()=>{
  CUR='auto_finish';
  let s = `<div style="${st(96,110,80,80)}border-radius:40px;background:rgba(48,164,108,.18);color:var(--ok);display:flex;align-items:center;justify-content:center">${ico('circle-check',44,null,2)}</div>`;
  s += tt(16,210,240,120,'msg',{a:'c'},'msg') + tb(12,420,248,46,'ok',{v:'primary'},'ok');
  return screen('auto_finish', s);
});

S('shaping_done','Calibration','Input shaping done',()=>{
  CUR='syntony_finish';
  let s = `<div style="${st(96,110,80,80)}border-radius:40px;background:rgba(48,164,108,.18);color:var(--ok);display:flex;align-items:center;justify-content:center">${ico('circle-check',44)}</div>`;
  s += tt(16,210,240,120,'msg',{a:'c'},'msg') + tb(12,420,248,46,'ok',{v:'primary'},'ok');
  return screen('syntony_finish', s);
});
