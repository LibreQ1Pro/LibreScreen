// ---- screens: settings, network, keyboard --------------------------------------------------------------------------
S('settings','Settings and network','Settings',()=>{
  CUR='common_set';
  let s = tabs('l','r','r',['tab_calib','tab_settings']);
  [['lang_lbl','lang_btn'],['network_lbl','network_btn'],['sysinfo_lbl','sysinfo_btn'],['sleep_lbl','sleep_btn']].forEach((r,i)=>{ s += row(12,60+60*i,248,52,T(r[0]),{chev:1},r[1]); });
  s += row(12,300,248,52,esc(caption('about')),{chev:1},'about_btn');
  // the last row is "Restore Factory Settings" (an action: no chevron, red label); while the setup guide is switched on it is "Setup Guide" with its switch on (touching it switches the guide off, and the row is "Restore Factory Settings" again)
  s += isV('guide') ? row(12,360,248,52,T('guide_txt'),{sw:true},'reset_btn') : row(12,360,248,52,T('reset_lbl').replace('<br>',' '),{},'reset_btn').replace('class="t ','class="t red ');
  s += nav('settings');
  return screen('common_set', s);
}, 'The last row is "Restore Factory Settings"; while the setup guide is switched on the host shows "Setup Guide" there instead.',
 {variants:[{id:'reset',label:'Restore'},{id:'guide',label:'Setup guide'}]});

// the tiles of the language pages: the order of the names is the value of the screen's `lang`; the tile of the current language is selected
const LANG_NAMES1 = ['lang_cn','lang_ru','lang_en','lang_jp','lang_fr','lang_de','lang_it','lang_es'];
const LANG_NAMES2 = ['lang_kr','lang_pt','lang_ar','lang_tr','lang_he'];
function langTiles(names, first, top, page){
  let s = '';
  names.forEach((n,i)=>{
    const x=12+128*(i%2), y=top+68*Math.floor(i/2), sel=(first+i===lang);
    s += `<div${nm(n)} title="${tip(n,x,y,120,60)}" style="${st(x,y,120,60)}background:${sel?'var(--btn-hi)':'var(--btn)'};border-radius:12px"></div>`+
         `<div class="radio${sel?' on':''}" style="left:${x+10}px;top:${y+19}px"></div>` + txt(x+36,y,82,60,T(n+'_name',page),{num:1},n+'_name');
  });
  return s;
}
S('language','Settings and network','Language',()=>{
  CUR='language';
  let s = header(T('title'));
  s += langTiles(LANG_NAMES1,0,60,'language');
  s += btn(12,340,120,44,'',{icon:'chevron-up',is:24,v:'dim'},'prev_page')+btn(140,340,120,44,'',{icon:'chevron-down',is:24},'next_page');
  s += nav('settings');
  return screen('language', s);
});
S('language_2','Settings and network','Language, page 2',()=>{
  CUR='language2';
  let s = header(T('title','language'));
  s += langTiles(LANG_NAMES2,8,60,'language2');
  s += btn(12,340,120,44,'',{icon:'chevron-up',is:24},'prev_page')+btn(140,340,120,44,'',{icon:'chevron-down',is:24,v:'dim'},'next_page');
  s += nav('settings');
  return screen('language2', s);
});

S('screen','Settings and network','Screen (sleep, brightness)',()=>{
  CUR='sleep_mode';
  let s = header(T('title'));
  const chosen = VARIANT || 'opt_5min';
  s += txt(12,56,248,20,caption('sleephint'),{role:'t16'},'sleep_hint');
  ['opt_5min_lbl','opt_15min_lbl','opt_30min_lbl','opt_never_lbl'].forEach((o,i)=>{ const id = o.replace('_lbl',''), on = id === chosen; s += row(12,84+56*i,248,48,T(o),{radio:on,sel:on},id); });
  s += txt(12,308,200,28,T('brightness_lbl'),{role:'t16'},'brightness_lbl') + pctValue(176,308,84,28,'80','bright_val',{align:'r'});
  s += slider(12,344,248,80,'bright_slider',{min:10,max:100});
  s += nav('settings');
  return screen('sleep_mode', s);
}, 'The brightness slider is a native slider (track 10, knob 28, touch region 44 high), 10..100.',
 {variants:[{id:'opt_5min',label:'5 minutes'},{id:'opt_15min',label:'15 minutes'},{id:'opt_30min',label:'30 minutes'},{id:'opt_never',label:'Never'}]});

S('klipper_status','Settings and network','Klipper status',()=>{
  CUR='sys_ok';
  let s = header(T('title'));
  s += card(12,56,248,148,'') + `<div style="${st(104,72,64,64)}border-radius:32px;background:rgba(48,164,108,.16);color:var(--ok);display:flex;align-items:center;justify-content:center">${ico('circle-check',34)}</div>`;
  s += tt(24,144,224,48,'msg',{a:'c'},'msg');
  // the same three buttons as on the error page, at the same places
  s += btn(12,212,248,46,T('export_logs'),{},'export_logs')+btn(12,266,248,46,T('restart_klip','reset'),{},'restart_klip')+btn(12,320,248,46,T('restart_fw','reset'),{v:'danger'},'restart_fw');
  s += nav('settings');
  return screen('sys_ok', s);
});
S('klipper_error','Settings and network','Klipper error',()=>{
  CUR='reset';
  const long = isV('long');
  let s = header(T('title'));
  // the message of Klipper has any length: it scrolls in its own area
  s += card(12,56,248,148,'') + `<div style="${st(24,68,28,28)}color:var(--danger)">${ico('triangle-alert',26)}</div>` +
       scrollBox(60,64,190,132,long?esc(LONG_ERROR):T('err_msg'),{role:'t16',bar:long},'err_msg');
  s += btn(12,212,248,46,T('export_logs'),{},'export_logs')+btn(12,266,248,46,T('restart_klip'),{},'restart_klip')+btn(12,320,248,46,T('restart_fw'),{v:'danger'},'restart_fw');
  s += nav('settings');
  return screen('reset', s);
}, 'The error text scrolls inside its area (the thumb at the right shows there is more); nothing is cut off silently.',
 {variants:[{id:'stock',label:'Stock text'},{id:'long',label:'Long error'}]});

// network
const NT = k => T(k,'net');
const NET_IP = '192.168.1.57';
function netList(page, top, withChips){
  // the names of the networks come from the host: a long one is cut to the slot of the row. The looks of a row (host: face(row, state)): plain,
  // with a check (the connected network); the buttons below are dim at the end of the list. VARIANT: 'plain' = every row plain, both buttons usable;
  // 'checks' = every row checked, the next button dim; the first variant is the page as it is on its first sheet.
  const names=['Home-Network','Printer-AP','Neighbour_5G','Guest-Network-With-A-Very-Long-Name','Cafe Free WiFi'];
  let s='';
  names.forEach((n,i)=>{ const check = isV('checks') || (!isV('plain') && i===0);
    s += row(12,top+52*i,248,44,n,{check:check,cut:true},'row'+(i+1)); });
  const prevDim = !isV('plain') && !isV('checks'), nextDim = isV('checks');
  s += btn(12,364,120,40,'',{icon:'chevron-up',is:22,v:prevDim?'dim':''},'prev_btn')+btn(140,364,120,40,'',{icon:'chevron-down',is:22,v:nextDim?'dim':''},'next_btn');
  return s;
}
const NETLIST_VARIANTS = [{id:'first',label:'First sheet'},{id:'plain',label:'Plain rows'},{id:'checks',label:'Checked rows'}];
S('wifi_list','Settings and network','Wi-Fi list',()=>{
  CUR='wifi_list';
  let s = header(T('title'));
  s += tb(12,56,96,40,'saved_btn',{},'saved_btn')+tb(116,56,96,40,'hidden_btn',{},'hidden_btn')+btn(220,56,40,40,'',{icon:'rotate-cw',is:20},'refresh_btn');
  s += netList('wifi_list',104);
  s += nav('settings');
  return screen('wifi_list', s);
}, '', {variants:NETLIST_VARIANTS});
S('saved_networks','Settings and network','Saved networks',()=>{
  CUR='net_saved';
  let s = header(T('title'));
  s += netList('net_saved',56);
  s += nav('settings');
  return screen('net_saved', s);
}, '', {variants:NETLIST_VARIANTS});
S('network_details','Settings and network','Network details',()=>{
  CUR='net_detail';
  let s = header(T('title'));
  s += card(12,56,248,84,'') + txt(26,62,220,28,nameHTML('Home-Network',220,DYNAMIC_ROLE,1,{ext:false}),{role:DYNAMIC_ROLE,num:1,dyn:1},'ssid_txt') +
       txt(26,96,220,34,nameHTML(NT('connected').replace(/<br>/g,' ')+' · '+NET_IP,220,'t13',1,{ext:false}),{role:'t13',mute:1,num:1},'status_txt');
  s += btn(12,148,248,46,NT('disconnect'),{v:'primary'},'connect_btn')+tb(12,202,248,46,'passwd_btn',{},'passwd_btn');
  s += row(12,256,248,46,NT('autoconnect').replace(': ',''),{sw:!isV('auto_off')},'auto_btn')+tb(12,310,248,46,'forget_btn',{v:'danger'},'forget_btn');
  s += nav('settings');
  return screen('net_detail', s);
}, '', {variants:[{id:'auto_on',label:'Autoconnect on'},{id:'auto_off',label:'Autoconnect off'}]});
S('forget_network','Settings and network','Forget network?',()=>{
  CUR='net_confirm';
  let s = header(T('title'));
  s += card(12,56,248,170,'') + `<div style="${st(112,68,48,48)}color:var(--danger)">${ico('triangle-alert',40)}</div>`;
  // the name of the network comes from the host: the same wide font as the other lines, white where the others are muted
  s += txt(28,122,216,24,NT('forget_q'),{a:'c',num:1,mute:1},'msg') + txt(28,146,216,26,nameHTML('Home-Network',216,DYNAMIC_ROLE,1,{ext:false}),{role:DYNAMIC_ROLE,a:'c',num:1,dyn:1},'ssid_msg') + txt(28,172,216,44,NT('password_deleted'),{a:'c',mute:1,v:'top'},'msg2');
  s += btn(12,234,120,46,NT('forget'),{v:'danger'},'forget_btn')+btn(140,234,120,46,NT('cancel'),{},'cancel');
  s += nav('settings');
  return screen('net_confirm', s);
});
// the state of the two interfaces: each line is a label and a value (the value comes from the host: the wide font, cut to its slot);
// a connected interface shows SSID / IP / GW (Wi-Fi) or IP / GW (LAN), a disconnected one says so
const NET_STATES = [{id:'wifi',label:'Wi-Fi connected'},{id:'lan',label:'LAN connected'},{id:'both',label:'Both connected'},{id:'none',label:'Nothing connected'}];
S('network_info','Settings and network','Network info',()=>{
  CUR='net_info';
  const st_ = VARIANT || 'wifi', wifi = st_==='wifi'||st_==='both', lan = st_==='lan'||st_==='both';
  const none = '---';
  const line = (y,label,value,name) => txt(24,y,56,24,esc(label),{role:'t16',mute:1,num:1},name+'_l') + txt(82,y,166,24,nameHTML(value,166,DYNAMIC_ROLE,1,{ext:false}),{role:DYNAMIC_ROLE,num:1,dyn:1},name);
  const iface = (y,value,name) => txt(108,y,140,26,nameHTML(value,140,DYNAMIC_ROLE,1,{ext:false}),{role:DYNAMIC_ROLE,a:'r',mute:1,num:1,dyn:1},name);
  let s = header(T('title'));
  s += card(12,56,248,128,'') + `<div style="${st(24,66,22,22)}color:var(--accent)">${ico('wifi',22)}</div>` + txt(54,64,52,26,'Wi-Fi',{role:'t19'},null) + iface(64,'wlx40a5ef2378f6','wifi_if');
  s += line(96,'SSID:',wifi?'Home-Network':none,'wifi_ssid')+line(120,'IP:',wifi?NET_IP:none,'wifi_ip')+line(144,'GW:',wifi?'192.168.1.1':none,'wifi_gw');
  s += card(12,192,248,104,'') + `<div style="${st(24,202,22,22)}color:var(--text2)">${ico('ethernet-port',22)}</div>` + txt(54,200,52,26,'LAN',{role:'t19'},null) + iface(200,'eth0','lan_if');
  s += line(232,'IP:',lan?'192.168.1.60':none,'lan_ip')+line(256,'GW:',lan?'192.168.1.1':none,'lan_gw');
  s += row(12,304,248,50,'Wi-Fi',{sw:wifi},'radio_btn');
  s += row(12,362,248,52,NT('wifi_networks'),{chev:1},'wifi_btn');
  s += nav('settings');
  return screen('net_info', s);
}, 'The first page of the network settings (Settings > Network). Each interface is a card with its name at the right and the lines "label: value" (SSID, IP, GW for Wi-Fi; IP, GW for LAN); a value that is not known is "---". The Wi-Fi switch turns the radio on and off, the last row opens the list of Wi-Fi networks.',
 {variants:NET_STATES.map(x=>({id:x.id,label:x.label}))});

// the Wi-Fi keyboard: kbmode of the stock page (1 / 2 password, 3 hidden network name, 4 hidden network password)
S('wifi_keyboard','Keyboards','Text keyboard (Wi-Fi)',()=>{
  CUR='wifi_kb';
  const ssid = isV('ssid'), upper = isV('upper'), sym = isV('sym'), okDim = isV('ok_dim');
  let s = header(ssid ? caption('ssid') : T('title'));
  // the password shows asterisks (the `pw` attribute of the text widget); a network name is shown as typed
  s += card(12,56,248,48,'background:#101010') +
       (ssid ? txt(24,56,224,48,'Home-Net',{role:'t19',num:1},'input_show') + rect(24+textW('Home-Net','t19')+2,68,2,24,'var(--accent)',1)
             : txt(24,56,224,48,'********',{role:'t19',num:1},'input_show'));
  const letters='abcdefghijklmnopqrstuvwxyz';
  for(let i=0;i<26;i++){ const c=i%4,r=Math.floor(i/4); s += `<div class="key k19"${nm('key_'+letters[i])} title="${tip('key_'+letters[i],12+52*c,112+48*r,44,40)}" style="${st(12+52*c,112+48*r,44,40)}">${upper?letters[i].toUpperCase():letters[i]}</div>`; }
  s += `<div class="key fn"${nm('key_space')} title="${tip('key_space',116,400,96,40)}" style="${st(116,400,96,40)}">${ico('space',26)}</div>`;
  s += `<div class="key fn"${nm('key_del')} title="${tip('key_del',220,112,40,88)}" style="${st(220,112,40,88)}">${ico('delete',20)}</div>`;
  // the shift key has three looks: lower case, upper case (blue), and on the pages of symbols the number of the page
  s += sym ? `<div class="key fn k19"${nm('key_shift')} title="${tip('key_shift',220,208,40,88)}" style="${st(220,208,40,88)}">1/2</div>`
           : `<div class="key fn${upper?' on':''}"${nm('key_shift')} title="${tip('key_shift',220,208,40,88)}" style="${st(220,208,40,88)}${upper?';background:var(--accent);color:#fff':''}">${ico('arrow-big-up',22,upper?'#fff':null)}</div>`;
  s += `<div class="key fn k19"${nm('key_sym')} title="${tip('key_sym',220,304,40,40)}" style="${st(220,304,40,40)}">${sym?'abc':'123'}</div>`;
  s += `<div class="key${okDim?' off':''}"${nm('key_ok')} title="${tip('key_ok',220,352,40,88)}" style="${st(220,352,40,88)}${okDim?'':';background:var(--accent)'}">${ico('check',24,okDim?'currentColor':'#fff',2.5)}</div>`;
  return screen('wifi_kb', s);
}, 'The same keyboard asks for a password (asterisks) or for the name of a hidden network (kbmode 3, shown as typed). The shift key is blue in upper case and shows the page (1/2, 2/2) on the symbols; OK is dim until the text is long enough.',
 {variants:[{id:'password',label:'Password'},{id:'ssid',label:'Network name'},{id:'upper',label:'Upper case'},{id:'sym',label:'Symbols'},{id:'ok_dim',label:'OK dim'}]});
S('wifi_connecting','Settings and network','Connecting',()=>{
  CUR='wifi_connect';
  return screen('wifi_connect', busy('msg'));
});
// the page Wi-Fi Connection that is shown when there is no network (project page 'internet')
S('wifi_no_network','Settings and network','Wi-Fi: no network',()=>{
  CUR='internet';
  let s = header(T('title'));
  s += txt(12,56,200,40,'',{role:'t16',num:1},'ip_txt') + btn(220,56,40,40,'',{icon:'rotate-cw',is:20},'refresh_btn');
  s += `<div style="${st(112,170,48,48)}color:var(--text3)">${ico('wifi-off',44)}</div>`;
  s += tt(24,230,224,60,'msg',{a:'c',mute:1},'msg');
  s += nav('settings');
  return screen('internet', s);
}, 'The page shown while no network is found: the IP field is empty until a link is up (the stock page has it blank), refresh looks again.');
// the screen is asleep: backlight 0, the whole page is one touch region
S('screen_asleep','Settings and network','Screen asleep',()=>{
  CUR='screen_sleep';
  return screen('screen_sleep', rect(0,0,272,480,'#000') + hit(0,0,272,480,'touch'));
}, 'Black: the page sets dim=0 and has no widget but a touch capture; any touch wakes the screen and the previous page is restored by the host. Nothing is drawn on it.');
// the loading spinner: the animation `spinner` of the project (12 frames, tools/make_spinner.py); the mockup plays the same frames
function spinner(x,y){
  return box(x,y,40,40,'anim',animImg('spinner',0,0),'spin','background:transparent;border-radius:0;overflow:hidden');
}
function busy(key){
  return spinner(116,170) + tt(24,226,224,100,key,{a:'c',v:'top'},key);
}
