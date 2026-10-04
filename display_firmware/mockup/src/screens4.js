// ---- screens: pop-ups, guide, boot ---------------------------------------------------------------------------------
// A pop-up card: the height is a profile (324 normally, 384 for the long texts); the message gets the room between the icon and the buttons.
// o.h: height of the card; o.scroll: the message scrolls in its own area (an error of any length)
function popup(page, kind, msgs, btns, o){
  o = o || {};
  CUR = page;
  const col = {info:'var(--accent)',warn:'var(--warn)',error:'var(--danger)',ok:'var(--ok)',ask:'var(--accent)'}[kind];
  const g = {info:'info',warn:'triangle-alert',error:'octagon-x',ok:'circle-check',ask:'info'}[kind];
  const h = o.h || 324, y0 = o.h ? Math.round((480-h)/2/8)*8 : 84, by = y0+h-72;
  let s = rect(0,0,272,480,'#101010');
  s += `<div class="popup" style="${st(12,y0,248,h)}"></div>`;
  s += `<div style="${st(112,y0+16,48,48)}border-radius:24px;background:color-mix(in srgb, ${col} 18%, transparent);color:${col};display:flex;align-items:center;justify-content:center">${ico(g,26)}</div>`;
  if (o.scroll) s += scrollBox(28,y0+74,216,h-154,isV('long')?esc(LONG_ERROR):T(msgs[0]),{role:DYNAMIC_ROLE,bar:isV('long'),css:'text-align:center'},msgs[0]);
  else {
    // the message sits in the middle of the room between the icon and the buttons (xcen = 1, ycen = 1 of the stock widget); with two texts the first
    // is bottom-aligned above the middle and the second top-aligned below it (the stock page: ycen 2 and 0)
    const top = y0+68, room = by-6-top;
    if (msgs.length === 1) s += tt(28,top,216,room,msgs[0],{a:'c',role:'t16'},msgs[0]);
    else { const hh = Math.floor((room-8)/2); s += tt(28,top,216,hh,msgs[0],{a:'c',v:'bottom',role:'t16'},msgs[0]) + tt(28,top+hh+8,216,hh,msgs[1],{a:'c',v:'top',sz:'l'},msgs[1]); }
  }
  if (btns.length === 1) s += tb(28,by,216,48,btns[0][0],{v:btns[0][1]||'primary'},btns[0][0]);
  else s += tb(28,by,104,48,btns[0][0],{v:btns[0][1]||'primary',wrap:1},btns[0][0]) + tb(140,by,104,48,btns[1][0],{v:btns[1][1]||'',wrap:1},btns[1][0]);
  return screen(page, s);
}
const POPS = [
  ['open_pop','ask',['msg'],[['ok','primary'],['cancel','']],'Setup guide: skip?'],
  ['print_finish','ok',['msg','time_txt'],[['ok','primary']],'Print complete'],
  ['print_stop','ask',['msg'],[['ok','danger'],['cancel','']],'Stop printing?'],
  ['stop_confirm','ask',['msg'],[['ok','danger'],['cancel','']],'Stop: are you sure?'],
  ['resume_print','ask',['msg'],[['ok','primary'],['cancel','']],'Resume the last print?'],
  ['print_no_fil','warn',['msg'],[['ok','primary']],'No filament'],
  ['print_no_fil2','warn',['msg'],[['ok','primary']],'Filament tangle'],
  ['print_lowtemp','warn',['msg'],[['ok','primary']],'Nozzle too cold'],
  ['preview_pop_1','warn',['msg'],[['ok','primary'],['no_more','']],'Closed chamber warning'],
  ['preview_pop_2','warn',['msg'],[['ok','primary'],['no_more','']],'Doors and cover'],
  ['move_pop_1','warn',['msg'],[['ok','primary']],'Out of range'],
  ['move_pop_2','ask',['msg'],[['ok','primary'],['cancel','']],'Home the axes?'],
  ['filament_pop_1','warn',['msg'],[['ok','primary']],'Nozzle temperature too low'],
  ['unload_finish','ok',['msg'],[['ok','primary']],'Unloading done'],
  ['auto_warning','warn',['msg'],[['ok','primary']],'Set the temperature'],
  ['cal_warning','warn',['msg'],[['next_btn','primary'],['back_btn','']],'Before calibrating'],
  ['level_error','error',['msg'],[['ok','primary']],'Leveling error'],
  ['detect_error','error',['msg'],[['ok','primary']],'Error',{scroll:true}],
  ['gcode_error','error',['msg'],[['ok','primary']],'G-code error',{scroll:true}],
  ['memory_warning','warn',['msg'],[['ok','primary']],'Memory is full'],
  ['restore_config','ask',['msg'],[['ok','danger'],['cancel','']],'Restore factory settings?'],
  ['update_success','ok',['msg'],[['ok','primary']],'Update complete'],
  ['print_log_s','ok',['msg'],[['ok','primary']],'Logs exported'],
  ['print_log_f','error',['msg'],[['ok','primary']],'Export failed'],
  ['wifi_success','ok',['msg'],[['ok','primary']],'Connected'],
  ['wifi_fail','error',['msg'],[['ok','primary']],'Connection failed'],
];
POPS.forEach(p=>S(newPage(p[0]),'Pop-ups',p[4],()=>popup(p[0],p[1],p[2],p[3],p[5]),
  p[5] && p[5].scroll ? 'The message of the error scrolls inside its area; the thumb of the bar shows that there is more.' : (p[5] && p[5].h ? 'A long text: the card is taller than the usual 324.' : ''),
  p[5] && p[5].scroll ? {variants:[{id:'stock',label:'Stock text'},{id:'long',label:'Long error'}]} : null));
['print_stopping','re_printing','syntony_move','bed_moving'].forEach(id=>S(newPage(id),'Pop-ups',{print_stopping:'Stopping',re_printing:'Resuming',syntony_move:'Input shaping',bed_moving:'Moving the bed'}[id],()=>{CUR=id;return screen(id,busy('msg'));}));

// -- guide
// the animations of the project are 256 x 200 (the setup videos) and 212 x 150 (the wizards): "real" puts the frames as they are drawn (the setup
// videos where the stock project has them, at (8, 40)); "mockup" is the block the first mockup had, the frames at their size in the middle of it (cropped)
const VIDEO_VARIANTS = null;
const VIDEO_NOTE = 'The frames are the project\'s own pictures (animations/), 248 x 192 with rounded corners drawn in; they play at 1.5 s a frame.';
const videoBlock = key => animBlock(12,48,248,192,key,'anim');
function guide(page, title, body){ CUR=page; return screen(page, txt(12,8,248,32,title,{sz:'l'},'title') + body); }
function nextRound(x,y){ return btn(x,y,64,64,'',{icon:'chevron-right',is:30,v:'primary',css:'border-radius:32px'},'next'); }
// the language tiles of the first start (the same order as on the settings pages)
function openLangTiles(names, first, top){
  let s = '';
  names.forEach((n,i)=>{
    const x=12+128*(i%2), y=top+68*Math.floor(i/2), sel=(first+i===lang);
    s += `<div${nm(n)} title="${tip(n,x,y,120,60)}" style="${st(x,y,120,60)}background:${sel?'var(--btn-hi)':'var(--btn)'};border-radius:12px"></div><div class="radio${sel?' on':''}" style="left:${x+10}px;top:${y+19}px"></div>`+txt(x+36,y,82,60,T(n+'_name'),{num:1},n+'_name');
  });
  return s;
}
S('setup_language','Setup guide','Language (first start)',()=>{
  CUR='open_language';
  let s = txt(16,8,240,32,T('title'),{sz:'l'},'title');
  s += openLangTiles(LANG_NAMES1,0,52);
  s += btn(12,330,120,44,'',{icon:'chevron-up',is:24,v:'dim'},'prev_page')+btn(140,330,120,44,'',{icon:'chevron-down',is:24},'next_page');
  s += tb(12,424,120,46,'skip',{},'skip')+tb(140,424,120,46,'next',{v:'primary'},'next');
  return screen('open_language', s);
});
S('setup_language_2','Setup guide','Language (first start), page 2',()=>{
  CUR='open_language2';
  let s = txt(16,8,240,32,T('title'),{sz:'l'},'title');
  s += openLangTiles(LANG_NAMES2,8,52);
  s += btn(12,330,120,44,'',{icon:'chevron-up',is:24},'prev_page')+btn(140,330,120,44,'',{icon:'chevron-down',is:24,v:'dim'},'next_page');
  s += tb(12,424,120,46,'skip',{},'skip')+tb(140,424,120,46,'next',{v:'primary'},'next');
  return screen('open_language2', s);
}, 'The second sheet of the first-start picker: five languages, the tile of the current one is selected; "previous" goes back, the next sheet does not exist. The header keeps "(1/3)": it is the number of the setup step.');
S('setup_unbox_1','Setup guide','Unboxing',()=>{CUR='open_video_1';return guide('open_video_1',T('title'),videoBlock('video_remove_ties')+tt(12,252,248,70,'msg',{a:'c'},'msg')+nextRound(196,404));},VIDEO_NOTE,VIDEO_VARIANTS);
S('setup_unbox_warning','Setup guide','Unboxing: warning',()=>{CUR='open_warning';return guide('open_warning',T('title'),`<div style="${st(112,70,48,48)}border-radius:24px;background:rgba(245,165,36,.18);color:var(--warn);display:flex;align-items:center;justify-content:center">${ico('triangle-alert',26)}</div>`+tt(20,132,232,240,'msg',{a:'c',v:'top'},'msg')+btn(12,418,248,48,'',{icon:'chevron-right',is:28,v:'primary'},'next'));});
S('setup_load_insert','Setup guide','Load filament: insert',()=>{CUR='filamentVideo1';return guide('filamentVideo1',T('title'),videoBlock('video_push_filament')+tt(12,252,248,110,'msg',{a:'c'},'msg')+nextRound(196,404));},VIDEO_NOTE,VIDEO_VARIANTS);
S('setup_load_heat','Setup guide','Load filament: heat',()=>{
  CUR='filamentVideo2';
  let s = txt(16,8,240,32,T('title'),{sz:'l'},'title');
  s += heatEdit(12,52,248,'nozzle','220','220',true,'heat',{whole:true});
  s += btn(12,110,120,46,'',{icon:'minus',is:26},'temp_down')+btn(140,110,120,46,'',{icon:'plus',is:26},'temp_up');
  // the wait notice is a warning block, like the one of the calibration menu: the card, the warning icon and the text (white, not coloured)
  s += tt(16,176,240,84,'msg_heat',{a:'c',mute:1},'msg_heat');
  s += card(12,264,248,132,'') + `<div style="${st(116,272,40,40)}border-radius:20px;background:color-mix(in srgb, var(--warn) 18%, transparent);color:var(--warn);display:flex;align-items:center;justify-content:center">${ico('triangle-alert',22)}</div>`;
  // the next button waits for the temperature: dim (and the host switches its touch off) until the nozzle has reached the target
  s += tt(24,320,224,68,'msg_wait',{a:'c'},'msg_wait') + (isV('ready') ? nextRound(196,404) : btn(196,404,64,64,'',{icon:'chevron-right',is:30,v:'dim',css:'border-radius:32px'},'next'));
  return screen('filamentVideo2', s);
}, 'The next button is dim while the nozzle is heating (the page says so in the warning block) and blue once the target is reached.',
 {variants:[{id:'heating',label:'Heating (next waits)'},{id:'ready',label:'Hot (next ready)'},{id:'heat_on',label:'Heater on'},{id:'heat_off',label:'Heater off'}]});
S('setup_load_extrude','Setup guide','Load filament: extrude',()=>{
  CUR='filamentVideo3';
  let s = txt(12,8,248,32,T('title'),{sz:'l'},'title') + videoBlock('video_extrude');
  s += btn(86,248,100,44,'',{icon:'arrow-down',is:24},'extrude') + tt(12,300,248,110,'msg',{a:'c',mute:1},'msg') + btn(12,418,248,48,'',{icon:'chevron-right',is:28,v:'primary'},'next');
  return screen('filamentVideo3', s);
},VIDEO_NOTE,VIDEO_VARIANTS);
S('setup_done','Setup guide','Guide finished',()=>{
  CUR='open_finish';
  let s = `<div style="${st(96,60,80,80)}border-radius:40px;background:rgba(48,164,108,.18);color:var(--ok);display:flex;align-items:center;justify-content:center">${ico('circle-check',44)}</div>`;
  s += tt(16,160,240,100,'msg',{a:'c',sz:'l'},'msg') + tt(16,262,240,120,'msg_level',{a:'c',mute:1},'msg_level') + tb(12,418,248,48,'finish',{v:'primary'},'finish');
  return screen('open_finish', s);
});
// The steps of the filament wizards, as in the stock pages: step 1 is the hint with its animation below it, then heating (the temperature under
// it), the work itself and "done". The active step is a blue circle and its text is white; the host moves it on.
const WIZ = [{id:'start',label:'1 Hint',active:0},{id:'heating',label:'2 Heating',active:1},{id:'working',label:'3 Working',active:2},{id:'done',label:'4 Done',active:3}];
function wizardPage(page, animKey, doneBtn){
  CUR = page;
  const w = WIZ.find(x=>x.id===VARIANT) || WIZ[0];
  const items = [{y:20,h:60,html:T('hint'),name:'hint'},{y:240,h:24,html:T('step1_txt'),name:'step1_txt'},{y:303,h:60,html:T('step2_txt'),name:'step2_txt'},{y:365,h:60,html:T('step3_txt'),name:'step3_txt'}];
  let s = wizSteps(items,w.active) + animBlock(50,82,212,150,animKey,'anim');
  if (w.active >= 1) s += `<div style="${st(50,271,18,18)}color:var(--text2)">${hico('nozzle',18)}</div>` + heatValue(74,266,186,28,{cur:'250',tar:'250',on:false,name:'nozzle',big:false});     // shown from the heating step on
  if (w.id === 'done') s += tb(12,428,120,40,'alt_btn',{},'alt_btn') + tb(140,428,120,40,doneBtn,{v:'primary'},doneBtn);
  else s += tb(12,428,120,40,'back_btn',{},'back_btn') + tb(140,428,120,40,'next_btn',{v:'primary'},'next_btn');
  return screen(page, s);
}
const WIZ_VARIANTS = WIZ.map(x=>({id:x.id,label:x.label}));
S('unload_steps','Setup guide','Unload filament (steps)',()=>wizardPage('filament_pop_2','video_cut_filament','done_btn'),
  'As in the stock page: the hint is step 1 with its animation (212 x 150, the frames of the project, redrawn for the new design) below it; the temperature appears under "Heating up". When it is done the two buttons are "Load" and "OK".',{variants:WIZ_VARIANTS});
S('load_steps','Setup guide','Load filament (steps)',()=>wizardPage('filament_pop_3','video_load_filament','done_btn'),
  'The same page for loading; the last step may have three lines; when it is done the two buttons are "Retry" and "Done".',{variants:WIZ_VARIANTS});
S('unload_choose','Setup guide','Unload: choose',()=>{
  CUR='unload_mode';
  let s = tt(16,12,240,100,'msg',{a:'c'},'msg');
  s += tb(12,124,248,52,'manual_btn',{},'manual_btn') + tt(16,182,240,60,'hint',{a:'c',mute:1,sz:'s'},'hint');
  s += tb(12,254,248,52,'auto_btn',{},'auto_btn') + tt(16,314,240,100,'warn',{a:'c',sz:'s',css:'color:var(--warn)'},'warn');
  s += tb(12,424,248,46,'back_btn',{},'back_btn');
  return screen('unload_mode', s);
});
const UNLOAD = [{id:'heating',label:'1 Heating',active:0},{id:'unloading',label:'2 Unloading',active:1},{id:'done',label:'3 Done',active:2}];
S('unload_auto','Setup guide','Automatic unload',()=>{
  CUR='auto_unload';
  const u = UNLOAD.find(x=>x.id===VARIANT) || UNLOAD[0];
  const items = [{y:20,h:24,html:T('step1_txt'),name:'step1_txt'},{y:144,h:48,html:T('step2_txt'),name:'step2_txt'},{y:268,h:48,html:T('step3_txt'),name:'step3_txt'}];
  let s = wizSteps(items,u.active) + `<div style="${st(50,53,18,18)}color:var(--text2)">${hico('nozzle',18)}</div>` + heatValue(74,48,186,28,{cur:'220',tar:'220',on:false,name:'nozzle',big:false});
  if (u.id === 'done') s += tb(12,368,248,46,'load_btn',{},'load_btn') + tb(12,422,248,46,'ok',{v:'primary'},'ok');
  return screen('auto_unload', s);
}, 'As in the stock page: the temperature is under "Heating up"; the two buttons appear when the unload is done. Equal pitch of the steps (124).',
 {variants:UNLOAD.map(x=>({id:x.id,label:x.label}))});
// preheat: a vertical list of the three temperatures (the choice is the radio, "next" goes on with it)
S('preheat','Setup guide','Preheat: choose temperature',()=>{
  CUR='pre_heat';
  let s = rect(0,0,272,480,'#101010') + `<div class="popup" style="${st(12,60,248,360)}"></div>`;
  s += tt(28,76,216,84,'msg',{a:'c',role:'t16'},'msg');
  ['220','250','300'].forEach((v,i)=>{
    const y=168+52*i, sel=(VARIANT||'t220')==='t'+v, name='temp_opt'+(i+1);
    s += `<div class="rowhit"${nm(name)} title="${tip(name,28,y,216,44)}" style="${st(28,y,216,44)}"><div style="${st(0,0,216,44)}background:${sel?'var(--btn-hi)':'var(--btn)'};border-radius:12px"></div><div class="radio${sel?' on':''}" style="left:12px;top:11px"></div></div>`;
    s += run(74,y,136,44,[{t:v,role:'d20',w:36,a:'r'},{t:'°C',role:'t13',w:18,a:'l',color:'var(--text2)'}],{gap:3});
  });
  s += tb(28,348,104,48,'back_btn',{},'back_btn')+tb(140,348,104,48,'next_btn',{v:'primary'},'next_btn');
  return screen('pre_heat', s);
}, 'A vertical list of 220, 250 and 300 (the temperatures the stock page offers): the radio picks one, "Next" goes on with it.',
 {variants:[{id:'t220',label:'220'},{id:'t250',label:'250'},{id:'t300',label:'300'}]});
// -- boot
S('boot_logo','Boot','Boot logo',()=>{
  CUR='logo';
  return screen('logo', `<img src="art/logo.png" alt="" style="${st(56,100,160,160)}">`+txt(16,330,240,50,T('boot_msg'),{a:'c',mute:1},'boot_msg'));
});
S('restart_needed','Boot','Restart needed',()=>{
  CUR='restart';
  return screen('restart', `<div style="${st(112,100,48,48)}color:var(--danger)">${ico('triangle-alert',44)}</div>`+txt(16,168,240,70,T('title'),{a:'c',sz:'l'},'title')+txt(24,250,224,120,T('hint'),{a:'c',mute:1},'hint'));
});
S('shutting_down','Boot','Shutting down',()=>{
  CUR='shutdown';
  return screen('shutdown', `<div style="${st(116,170,40,40)};color:var(--text2)">${ico('power-off',40)}</div>`+txt(16,230,240,50,T('msg'),{a:'c'},'msg'));
});

S('setup_unbox_2','Setup guide','Unboxing 2',()=>{CUR='open_video_2';return guide('open_video_2',T('title'),videoBlock('video_remove_screws')+tt(12,252,248,70,'msg',{a:'c'},'msg')+nextRound(196,404));},VIDEO_NOTE,VIDEO_VARIANTS);
S('setup_spool_holder','Setup guide','Filament holder',()=>{CUR='filamentVideo0';return guide('filamentVideo0',T('title'),videoBlock('video_spool_holder')+tt(12,252,248,110,'msg',{a:'c'},'msg')+nextRound(196,404));},VIDEO_NOTE,VIDEO_VARIANTS);
S('setup_wait','Setup guide','Please wait',()=>{CUR='open_moving';return guide('open_moving',T('title'),spinner(116,150)+tt(20,214,232,200,'msg',{a:'c',v:'top'},'msg'));});
