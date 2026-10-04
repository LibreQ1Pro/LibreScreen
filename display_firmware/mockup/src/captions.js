// ---- short captions that belong to the mockup, not to the extracted project texts (texts.json) -------------------------
// Order of the languages: zh ru en ja fr de it es ko pt ar tr he (the index is the screen's `lang`).
// These are drafts for the screen firmware: the page 'printing_2' has no caption widgets in the stock project.
const CAPTIONS = {
  speed:   ['速度','Скорость','Speed','速度','Vitesse','Tempo','Velocità','Velocidad','속도','Velocidade','السرعة','Hız','מהירות'],
  // the words of the stock keyboard title (Flow Rate); sentence case like the other two captions
  flow:    ['喷头流速','Поток','Flow rate','流量','Débit','Flussrate','Flusso','Flujo','압출량','Fluxo','معدل التدفق','Akış oranı','קצב זרימה'],
  zoffset: ['Z 偏移','Смещение Z','Z offset','Z オフセット','Décalage Z','Z-Versatz','Offset Z','Offset Z','Z 오프셋','Offset Z','إزاحة Z','Z ofseti','היסט Z'],
  // the button of the move page that releases the steppers (M84); no such text in the stock project
  motors:  ['关闭电机','Выключить моторы','Motors off','モーターオフ','Moteurs off','Motoren aus','Motori off','Motores off','모터 끄기','Motores off','إيقاف المحركات','Motorları kapat','כיבוי מנועים'],
  // the two arrows of the filament page: up retracts the filament (G1 E-n), down extrudes it (G1 En); no such texts in the stock project
  retract: ['回抽','Втянуть','Retract','引き戻し','Rétracter','Zurückziehen','Ritrai','Retraer','후퇴','Retrair','سحب','Geri çek','משוך'],
  extrude: ['挤出','Выдавить','Extrude','押し出し','Extruder','Extrudieren','Estrudi','Extruir','압출','Extrudir','بثق','Ekstrüde et','שיחול'],
  // the line above the options of the Screen page
  sleephint: ['息屏时间','Отключение экрана через','Turn the screen off after','画面を消すまでの時間','Éteindre l\'écran après','Bildschirm ausschalten nach','Spegni lo schermo dopo','Apagar la pantalla después de','화면 꺼짐 시간','Desligar a tela após','إيقاف الشاشة بعد','Ekranı kapatma süresi','כיבוי המסך לאחר'],
  // the new row of the settings page (the page it opens is not designed yet)
  about:   ['关于 LibreQ1Pro','О LibreQ1Pro','About LibreQ1Pro','LibreQ1Proについて','À propos de LibreQ1Pro','Über LibreQ1Pro','Informazioni su LibreQ1Pro','Acerca de LibreQ1Pro','LibreQ1Pro 정보','Sobre o LibreQ1Pro','حول LibreQ1Pro','LibreQ1Pro hakkında','אודות LibreQ1Pro'],
  // the IP field of the network page while there is no address (no such text in the stock project)
  notconn: ['未连接','Нет подключения','Not connected','未接続','Non connecté','Nicht verbunden','Non connesso','No conectado','연결 안 됨','Não conectado','غير متصل','Bağlı değil','לא מחובר'],
  // the stock page keybdB keeps the translated caption of the silent button under another key (mute_btn@sys0=7)
  mute:    null,
  // text of the "Wi-Fi password" keyboard when it asks for a hidden network name: the stock texts of the project (net.network_name)
  ssid:    null
};
// the mockup draws the screens with these two entries of the project texts; both are looked up in their own page only
function caption(key){
  const c = CAPTIONS[key];
  if (c) return c[lang] || c[2];
  if (key === 'mute') return Tx('mute_btn@sys0=7','keybdB');
  if (key === 'ssid') return Tx('network_name','net');
  return '';
}
// the example the UI-version warning of the main page shows when the screen and the firmware disagree
const VERSION_FIXTURE = {ui:100, soc:99};
// "no filament" style long error text for the scrolling error areas (an example, the real text comes from Klipper)
const LONG_ERROR = 'Klippy state: shutdown. MCU \'mcu\' shutdown: Timer too close. This generally occurs when the host has not been able to keep up with the demands of the MCU: check the CPU load, the USB cable and the log (klippy.log) for more details, then restart the firmware.';
// the animations of the project (../animations/<key>/NNN.png): the size of the frames, their number and the time of a frame
const ANIMS = {
  video_remove_ties:{w:248,h:192,n:4,ms:1500}, video_remove_screws:{w:248,h:192,n:3,ms:1500}, video_spool_holder:{w:248,h:192,n:5,ms:1500},
  spinner:{w:40,h:40,n:12,ms:80},
  video_push_filament:{w:248,h:192,n:3,ms:1500}, video_extrude:{w:248,h:192,n:3,ms:1500},
  // the wizard animations are the size of their block on the page (212 x 150)
  video_cut_filament:{w:212,h:150,n:5,ms:1500}, video_load_filament:{w:212,h:150,n:4,ms:1500}
};
// project pages the new design does not use any more: they have no screen and the audit does not ask for one (what replaces them)
const RETIRED_PAGES = {};      // pages of the project that the design does not draw (none: the pages that were not used any more are removed from the project)
// the examples of the audit: the widest values a value slot must hold (the slot never changes its size)
const FIXTURES = {
  temp:   [['0','0'],['5','60'],['35','100'],['220','220'],['350','350']],
  percent:['0','5','35','100','999'],
  zoffset:['0.000','-1.000','12.345','-99.999'],
  coord:  ['0.00','-0.50','245.00','-999.99'],
  input:  ['','0','5','220','350']
};
