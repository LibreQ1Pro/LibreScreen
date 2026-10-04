// ---- screens: Home, files, print ------------------------------------------------------------------------------------
const SCREENS = [];
// opts.variants: [{id,label}] = states of one page (a keyboard mode, a warning); the first one is the default.
function S(id, group, title, build, note, opts){ SCREENS.push({id, group, title, build, note, variants:(opts && opts.variants) || null}); }
const isV = id => VARIANT === id;

// a heater of the home page: the same icon and readout as the rows of the print page (current / target / unit)
function heaterTile(x,y,w,h,glyph,temp,tar,on,name){
  return box(x,y,w,h,'card hi','',name) +
    `<div style="${st(x+12,y+(h-26)/2,26,26)}color:${lit(on)?HOT:'var(--text2)'}">${hico(glyph,26)}</div>` +
    heatValue(x+44,y,w-50,h,{cur:temp,tar:tar,on:on,name:glyph,big:false,mid:true});
}
function iconTile(x,y,w,h,glyph,on,name,o){
  o = o || {};
  const bg = o.v==='danger' ? 'background:var(--danger-bg)' : on ? 'background:var(--accent)' : '';
  return box(x,y,w,h,'btn',ico(glyph,24,o.v==='danger'?'#ff8e94':on?'#fff':'var(--text2)',2),name,bg);
}

S('home','Home and files','Home',()=>{
  CUR='main';
  let s = '';
  s += `<div style="${st(176,10,22,22)}color:var(--text2)">${ico('usb',20)}</div><div style="${st(204,10,22,22)}color:var(--text2)">${ico('ethernet-port',20)}</div><div style="${st(232,10,22,22)}color:var(--text2)">${ico('wifi',20)}</div>`;
  s += box(12,38,248,198,'card hi','','last_file_btn');
  s += thumb(66,48,140,140,'last_file_pic');
  s += `<div style="${st(26,48,26,26)}background:#212021;border-radius:13px;opacity:.9"></div><div style="${st(30,52,18,18)}color:#ddd">${ico('clock',18)}</div>`;
  s += nameBox(24,190,224,40,'Benchy_PLA_0.2mm.gcode','t16',2,{a:'c'},'last_file_name');
  s += heaterTile(12,244,168,52,'nozzle','220','220',true,'nozzle_btn');
  s += heaterTile(12,304,168,52,'bed','60','60',true,'bed_btn');
  s += heaterTile(12,364,168,52,'chamber','35','0',false,'chamber_btn');
  s += iconTile(188,244,72,52,'lightbulb',true,'light_btn');
  s += iconTile(188,304,72,52,'volume-2',false,'beep_btn');
  s += iconTile(188,364,72,52,'octagon-x',false,'stop_btn',{v:'danger'});
  if (isV('ver_warning')) {
    // the UI of the screen and the firmware of the printer disagree: a panel with the warning and both versions; it has no button
    s += rect(8,118,256,244,'rgba(12,12,14,.94)',14);
    s += txt(20,130,232,150,Tx('ver_warning','main'),{role:'t16',a:'c',css:'color:#ff696b'},'ver_warning');
    s += run(24,300,224,24,[{t:'UI:',role:'t13',w:24,a:'l',color:'var(--text2)',name:'ui_ver_lbl'},{t:String(VERSION_FIXTURE.ui),role:'t13',w:36,a:'l',color:'var(--text)',name:'ui_ver'}],{gap:0});
    s += run(24,324,224,24,[{t:'SOC:',role:'t13',w:34,a:'l',color:'var(--text2)',name:'soc_ver_lbl'},{t:String(VERSION_FIXTURE.soc),role:'t13',w:36,a:'l',color:'var(--text)',name:'soc_ver'}],{gap:0});
  }
  s += nav('main');
  return screen('main', s);
}, 'Heaters are cards, the three switches are tiles: blue means on. Red value = the heater is on. The second state is the warning that the UI and the firmware versions differ (the stock page shows it until the versions match; it has no button).',
 {variants:[{id:'normal',label:'Normal'},{id:'no_values',label:'No values yet (---)'},{id:'ver_warning',label:'UI version warning'}]});

// The slots of the file list. VARIANT: 'mixed' = every slot a file (the page as the host first draws it), 'files' = the same, 'dirs' = every slot a folder (the folder is
// in the look of the slot), 'none' = no slot at all (nothing is drawn: the slot has no entry), 'mark' = the first slot is the last printed file (the host shows its mark),
// 'tab_usb' = the USB tab is selected, 'nav_on' / 'nav_off' = the three buttons below usable / dim (the looks the host switches).
S('file_list','Home and files','File list',()=>{
  CUR='filelist';
  const v = VARIANT || 'mixed';
  let s = tabs(v==='tab_usb'?'r':'l','r',v==='tab_usb'?'r':'l',['local_tab','usb_tab']);
  const entries = [[12,56,'Benchy_PLA.gcode'],[140,56,'models'],[12,212,'calibration_cube.gcode'],[140,212,'part_with_a_very_long_name.gcode']];
  entries.forEach((e,i)=>{
    const [x,y,name] = e;
    const kind = v === 'dirs' ? 'dir' : 'file';
    const id = 'file'+(i+1);
    if (v === 'none') { s += box(x,y,120,148,'','',id) + box(x+4,y+4,112,112,'thumb','',id+'_pic','background:transparent') + box(x+4,y+120,112,24,'t','',id+'_name'); return; }
    s += box(x,y,120,148,'card hi','',id);
    // the thumbnail is 112 x 112 (a multiple of 16: the screen's JPEG decoder shears a picture whose width is not), the name is one line of the wide font (16, a line is 20 high) under it
    if(kind==='dir') s += box(x+4,y+4,112,112,'thumb','',id+'_pic','background:transparent') + `<div style="${st(x+28,y+28,64,64)}color:var(--text2)">${ico('folder',64,'var(--text2)',1.5)}</div>`;
    else s += thumb(x+4,y+4,112,112,id+'_pic');
    // the name comes from the host: one line of the slot, the extension stays at the end
    s += nameBox(x+4,y+120,112,24,name,DYNAMIC_ROLE,1,{a:'c',css:'color:var(--text)'},id+'_name');
  });
  const off = v === 'nav_off';
  s += btn(12,372,77,40,'',{icon:'chevron-left',is:24,v:(off||v==='mixed'||v==='files'||v==='dirs'||v==='none'||v==='tab_usb')?'dim':''},'prev')+btn(97,372,78,40,'',{icon:'chevron-right',is:24,v:off?'dim':''},'next')+btn(183,372,77,40,'',{icon:'undo-2',is:22,v:off?'dim':''},'up_dir');
  s += nav('files');
  return screen('filelist', s);
}, 'A name is cut by the host to one line of its slot (112 x 24, the wide font 16) and keeps its extension; the thumbnails are 112 x 112: "part_with_…e.gcode".',
 {variants:[{id:'mixed',label:'Files'},{id:'dirs',label:'Every slot a folder'},{id:'none',label:'No slots'},{id:'tab_usb',label:'USB tab'},{id:'nav_on',label:'Buttons usable'},{id:'nav_off',label:'Buttons dim'}]});

S('file_preview','Home and files','File preview',()=>{
  CUR='preview';
  let s = thumb(12,12,152,152,'preview_pic');
  s += btn(172,12,88,72,'',{icon:'undo-2',is:30},'back_btn') + btn(172,92,88,72,'',{icon:'play',is:32,v:'primary'},'start_btn');
  s += card(12,172,248,96,'');
  const cell=(x,y,glyph,val,name)=>`<div style="${st(x,y+6,24,24)}color:var(--text2)">${ico(glyph,22)}</div>`+txt(x+34,y,72,36,val,{num:1},name);
  s += cell(26,180,'clock','03h05m','est_time')+cell(146,180,'ruler','7.9 m','fil_length')+cell(26,224,'spool','PLA','fil_type')+cell(146,224,'weight','24 g','fil_weight');
  // the two switches have a look for each state (host: face("level_btn" / "timelapse_btn", "on" / "off"))
  const lv = !isV('both_off'), tl = isV('both_on');
  s += row(12,276,248,46,T('level_lbl'),{sw:lv},'level_btn') + row(12,330,248,46,T('timelapse_lbl'),{sw:tl},'timelapse_btn');
  // the name of the file is under them (the host cuts it to one line)
  s += nameBox(12,386,248,22,PRINT_FILE,'t16',1,{a:'c'},'file_name');
  s += nav('files');
  return screen('preview', s);
}, '', {variants:[{id:'default',label:'Leveling on'},{id:'both_on',label:'Both on'},{id:'both_off',label:'Both off'}]});

// -- printing
// the rows of the two print pages: the same coordinates on both, so nothing jumps when the page is switched
const PRINT_LAYOUT = {rows:[222,288,354], rowH:58, actionsY:420, actionsH:48};
const PRINT_FILE = 'Benchy_PLA_0.2mm.gcode';
function printTop(page, paused){
  CUR=page;
  let s = thumb(12,12,132,132,'thumb');
  s += btn(152,12,108,62,'',{icon:paused?'play':'pause',is:30,v:paused?'primary':''},'pause_btn') + btn(152,82,108,62,'',{icon:'square',is:26,v:'danger'},'stop_btn');
  s += nameBox(12,150,248,26,PRINT_FILE,'t16',1,{a:'c'},'file_name');
  s += txt(12,178,80,22,'0h10m',{sz:'s',num:1},'time_elapsed') + pctValue(96,174,80,28,'35','progress_pct',{align:'c'}) + txt(180,178,80,22,'0h18m',{a:'r',sz:'s',num:1},'time_left');
  s += progress(12,206,248,8,35,'progress');
  return s;
}
function heatRow(x,y,w,glyph,cur,tar,on,name,h=50){
  return box(x,y,w,h,'card hi','',name) + `<div style="${st(x+12,y+(h-26)/2,26,26)}color:${lit(on)?HOT:'var(--text2)'}">${hico(glyph,26)}</div>` +
    heatValue(x+44,y,w-50,h,{cur:cur,tar:tar,on:on,name:glyph,big:false,mid:true});
}
function fanTile(x,y,w,h,i,val,name){
  return box(x,y,w,h,'card hi','',name) + `<div style="${st(x+10,y+(h-24)/2,24,24)}color:var(--text2)">${ico('fan',22)}</div>` +
    `<div class="t r-t13" style="${st(x+30,y+(h-24)/2+14,14,16)};color:var(--text3)"><span>${i}</span></div>` +
    slot(x+38,y,w-46,h,String(dv(val)),'d20',{a:'r',name:'fan'+i+'_val'});
}
function printFans(){
  return [100,0,60].map((val,i)=>fanTile(180,PRINT_LAYOUT.rows[i],80,PRINT_LAYOUT.rowH,i+1,val,'fan'+(i+1)+'_btn')).join('');
}
S('printing','Printing','Printing',()=>{
  let s = printTop('printing');
  [['nozzle',220,220,true],['bed',60,60,true],['chamber',35,0,false]].forEach((f,i)=>{
    const [glyph,cur,tar,on] = f;
    s += heatRow(12,PRINT_LAYOUT.rows[i],160,glyph,cur,tar,on,glyph+'_btn',PRINT_LAYOUT.rowH);
  });
  s += printFans();
  s += btn(12,PRINT_LAYOUT.actionsY,120,PRINT_LAYOUT.actionsH,'',{icon:'layers',is:24},'speed_btn')+btn(140,PRINT_LAYOUT.actionsY,120,PRINT_LAYOUT.actionsH,'',{icon:'octagon-x',is:24,v:'danger'},'flow_btn');
  return screen('printing', s);
}, 'Pause / stop are large tiles next to the thumbnail; the lower half is the heaters and fans; the two buttons at the bottom open page 2 and stop the machine. "No values yet": the digit fonts have "-", a value that the host has not sent shows "---".',
 {variants:[{id:'normal',label:'Values'},{id:'no_values',label:'No values yet (---)'},{id:'heat_on',label:'All heaters on'},{id:'heat_off',label:'All heaters off'}]});

S('print_adjust','Printing','Printing 2',()=>{
  let s = printTop('printing_2');
  // the captions are separate text widgets, not baked into the button pictures
  const tool = (y,glyph,val,key,unit)=>
    box(12,y,160,PRINT_LAYOUT.rowH,'card hi','',key+'_btn') +
    `<div style="${st(24,y+16,26,26)}color:var(--text2)">${HEAT[glyph]?hico(glyph,26):ico(glyph,26)}</div>` +
    txt(56,y+6,104,18,esc(caption(key)),{role:'t13',a:'r'},key+'_lbl') +
    (unit==='mm' ? zoffValue(56,y+24,104,30,val,key+'_val',{align:'r'}) : pctValue(56,y+24,104,30,val,key+'_val',{align:'r'}));
  s += tool(PRINT_LAYOUT.rows[0],'gauge','100','speed','%');
  s += tool(PRINT_LAYOUT.rows[1],'flow','100','flow','%');
  s += tool(PRINT_LAYOUT.rows[2],'arrow-up-down','-1.000','zoffset','mm');
  s += printFans();
  s += iconTile(12,PRINT_LAYOUT.actionsY,120,PRINT_LAYOUT.actionsH,'lightbulb',isV('light_off') ? false : true,'light2_btn');
  s += btn(140,PRINT_LAYOUT.actionsY,120,PRINT_LAYOUT.actionsH,'',{icon:'undo-2',is:24},'back_btn');
  return screen('printing_2', s);
}, 'Horizontal speed, flow and Z offset controls with captions; fans stay available on both print pages. Blue light tile = on; the bottom-right tile returns to the heaters.',
 {variants:[{id:'normal',label:'Values'},{id:'no_values',label:'No values yet (---)'},{id:'light_off',label:'Light off'}]});

function sheet(page, title, y, body){
  CUR=page;
  return rect(0,y,272,480-y,'var(--bg)') + rect(0,y,272,1,'var(--line)');
}

// the keyboard on a print page: the status stays visible in a compact top block, the keys are 44 high with 8 between them
// modes of the page: sys0 of the stock page (0 nozzle, 1 bed, 7 chamber, 2 speed, 3 flow, 4..6 fans)
const PRINT_KB = [
  {id:'nozzle',       label:'Nozzle',         sys:0, unit:'°C', val:'220'},
  {id:'nozzle_empty', label:'Nozzle, empty',  sys:0, unit:'°C', val:''},
  {id:'bed',          label:'Bed',            sys:1, unit:'°C', val:'60'},
  {id:'chamber',      label:'Chamber',        sys:7, unit:'°C', val:'35'},
  {id:'speed',        label:'Speed',          sys:2, unit:'%',  val:'100', mute:true},
  {id:'speed_mute',   label:'Speed, mute on', sys:2, unit:'%',  val:'100', mute:true, muted:true},
  {id:'flow',         label:'Flow',           sys:3, unit:'%',  val:'100'},
  {id:'fan1',         label:'Fan 1',          sys:4, unit:'%',  val:'100'},
  {id:'fan2',         label:'Fan 2',          sys:5, unit:'%',  val:'60'},
  {id:'fan3',         label:'Fan 3',          sys:6, unit:'%',  val:'0'}
];
S('print_keypad','Printing','Number keyboard (print)',()=>{
  const m = PRINT_KB.find(x=>x.id===(VARIANT||PRINT_KB[0].id)) || PRINT_KB[0];
  CUR='keybdB';
  let s = thumb(12,12,72,72,'thumb');
  s += btn(92,12,80,72,'',{icon:'pause',is:26},'pause_btn') + btn(180,12,80,72,'',{icon:'square',is:22,v:'danger'},'stop_btn');
  s += nameBox(12,90,248,22,PRINT_FILE,'t16',1,{a:'c'},'file_name');
  s += txt(12,116,80,24,'0h10m',{sz:'s',num:1},'time_elapsed') + pctValue(96,114,80,28,'35','progress_pct',{align:'c'}) + txt(180,116,80,24,'0h18m',{a:'r',sz:'s',num:1},'time_left');
  s += progress(12,146,248,6,35,'progress');
  s += rect(0,160,272,1,'var(--line)');
  // the silent mode button sits in the title row of the speed keyboard (the status block above does not change between the modes)
  s += btn(0,162,272,52,'',{icon:'chevron-left',is:26,css:'background:transparent;justify-content:flex-start;padding-left:11px;border-radius:0'},'back_btn') + txt(48,168,m.mute?170:212,40,Tx('title@sys0='+m.sys,'keybdB'),{role:'t16',num:0},'title');
  if (m.mute) s += btn(220,168,40,40,'',{icon:m.muted?'volume-x':'volume-2',is:22,v:m.muted?'primary':''},'mute_btn');
  s += numberInput(216,m.val,m.unit);
  ['1','2','3','4','5','6','7','8','9','del','0','ok'].forEach((k,i)=>{
    const c=i%3, r=Math.floor(i/3), off=m.muted;
    const cls = 'key' + (off ? ' off' : (k==='del'?' fn':''));
    const bg = (k==='ok' && !off) ? ';background:var(--accent)' : '';
    s += `<div class="${cls}"${nm('key_'+k)} title="${tip('key_'+k,[12,97,183][c],268+52*r,[77,78,77][c],44)}" style="${st([12,97,183][c],268+52*r,[77,78,77][c],44)}${bg}">${k==='del'?ico('delete',22):k==='ok'?ico('check',26,off?'currentColor':'#fff',2.5):k}</div>`;
  });
  return screen('keybdB', s);
}, 'On the print page the keyboard takes the lower part, the status stays visible. Speed mode has the silent button: while it is on the keys are off. Keys are 44 high, 8 apart; the last row ends 12 above the edge.',
 {variants:PRINT_KB.map(m=>({id:m.id,label:m.label}))});

S('print_z_offset','Printing','Z offset while printing',()=>{
  let s = printTop('print_zoffset');
  s += rect(0,222,272,258,'#212021')+rect(0,222,272,1,'var(--line)');
  s += btn(0,223,272,46,'',{icon:'chevron-left',is:26,css:'background:transparent;justify-content:flex-start;padding-left:11px;border-radius:0'},'back_btn') + txt(52,226,200,40,T('title'),{role:'t19'},'title');
  const steps=['0.01','0.05','0.1','0.5'], zi = {zs001:0, zs005:1, zs01:2, zs05:3}[VARIANT];
  steps.forEach((v,i)=>{ s += `<div class="btn${i===(zi==null?1:zi)?' primary':''}"${nm('step_'+v.replace('.',''))} title="${tip('step_'+v.replace('.',''),12+64*i,274,56,40)}" style="${st(12+64*i,274,56,40)}">${v}</div>`; });
  s += btn(12,322,120,52,'',{icon:'chevron-up',is:26},'z_up')+btn(140,322,120,52,'',{icon:'chevron-down',is:26},'z_down');
  s += txt(12,382,120,22,'G-code Z',{role:'t13',a:'c'},'gcode_z_lbl') + run(12,404,120,32,[{t:'0.200',role:'d20',w:76,a:'r',name:'gcode_z'}],{align:'c'});
  s += txt(140,382,120,22,'Offset',{role:'t13',a:'c'},'z_offset_lbl') + run(140,404,120,32,[{t:'-1.000',role:'d20',w:76,a:'r',name:'z_offset'}],{align:'c'});
  return screen('print_zoffset', s);
}, '', {variants:[{id:'zs005',label:'Step 0.05'},{id:'zs001',label:'Step 0.01'},{id:'zs01',label:'Step 0.1'},{id:'zs05',label:'Step 0.5'}]});

S('print_filament','Printing','Filament while printing',()=>{
  let s = printTop('print_filament', true);     // the print is paused: the blue play button resumes it
  s += rect(0,222,272,258,'#212021')+rect(0,222,272,1,'var(--line)');
  s += txt(12,226,248,36,T('title'),{role:'t19'},'title');
  s += heatRow(12,266,248,'nozzle',220,220,true,'heat_btn');
  s += btn(12,324,120,44,'',{icon:'minus',is:26},'temp_down')+btn(140,324,120,44,'',{icon:'plus',is:26},'temp_up');
  s += btn(12,376,56,52,'',{icon:'arrow-up',is:24},'retract_btn')+btn(76,376,56,52,'',{icon:'arrow-down',is:24},'extrude_btn')+tb(140,376,120,52,'replace_btn',{wrap:1},'replace_btn');
  return screen('print_filament', s);
}, '', {variants:[{id:'normal',label:'Heating'},{id:'heat_on',label:'Heater on'},{id:'heat_off',label:'Heater off'}]});
