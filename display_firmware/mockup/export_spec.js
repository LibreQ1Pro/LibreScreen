// Firmware export: labels are native text, never pixels inside a button tile.
function firmwareSpec(){
  const host=document.createElement('div'); host.style.cssText='position:absolute;left:0;top:0;width:272px;height:480px'; document.body.appendChild(host);
  const out=[];
  const rgb=c=>{ const m=(c.match(/\d+(\.\d+)?/g)||[]).map(Number); return m[3]===0?null:m.slice(0,3); };
  const kind=el=>['t','btn','hit','rowhit','bar','thumb','anim','key','card','step'].find(c=>el.classList.contains(c))||'box';
  function capture(sc,vid,li){
    host.innerHTML=renderScreen(sc,li,vid);
    const scr=host.querySelector('.scr'), origin=scr.getBoundingClientRect(), order=[...scr.querySelectorAll('*')];
    const geometry=el=>{const r=el.getBoundingClientRect();return {x:Math.round(r.left-origin.left),y:Math.round(r.top-origin.top),w:Math.round(r.width),h:Math.round(r.height)};};
    const matte=el=>{for(let p=el;p&&p!==scr;p=p.parentElement){ const c=rgb(getComputedStyle(p).backgroundColor);if(c)return c; }return [23,23,26];};
    const name=el=>el.dataset.w?el.dataset.w.replace(/^[^.]*\./,''):null;
    const usedHeight=el=>{const r=document.createRange();r.selectNodeContents(el);return Math.ceil(r.getBoundingClientRect().height);};
    const textStyle=el=>{
      const cs=getComputedStyle(el), role=(el.className.match(/\br-(t13|t16|t19|d20|d28|d32)\b/)||[])[1]||({13:'t13',16:'t16',19:'t19',20:'d20',28:'d28',32:'d32'}[Math.round(parseFloat(cs.fontSize))]||'t16');
      return {role,align:el.classList.contains('c')||cs.textAlign==='center'?'c':el.classList.contains('r')||cs.textAlign==='right'?'r':'l', color:rgb(cs.color),matte:matte(el),top:el.classList.contains('top'),bottom:el.classList.contains('bottom'),dyn:el.classList.contains('dyn'),scroll:el.classList.contains('scroll'),used:usedHeight(el)};
    };
    const widgets=[],prims=[],decor=[];
    scr.querySelectorAll('[data-w]').forEach(el=>{
      const cs=getComputedStyle(el), k=kind(el), item={...geometry(el),z:order.indexOf(el),name:name(el),kind:k,bg:rgb(cs.backgroundColor),radius:parseFloat(cs.borderTopLeftRadius)||0,labels:[]};
      if(k==='t')Object.assign(item,textStyle(el),{text:el.innerText});
      if(k==='anim'){const im=el.querySelector('[data-anim]');if(im)item.animation=im.dataset.anim;}
      if(k==='box'&&el.classList.contains('art')){const im=el.querySelector('img');if(im)item.art=im.getAttribute('src');}
      el.querySelectorAll('.t:not([data-w]),:scope > span:not(.ico)').forEach(child=>{
        if(child.closest('svg')||!child.innerText.trim())return;
        const rect=geometry(child);
        // Row slots are already fixed. A plain button label gets a fixed slot independent of its demo string.
        let centered=true;
        if(!child.classList.contains('t')){
          // the label of a button: as wide as the button, at its own height; centred when its middle is the middle of the button
          centered=Math.abs((rect.y+rect.h/2)-(item.y+item.h/2))<=3;
          const withIcon=!!el.querySelector('.ico') && !el.classList.contains('col');
          // a label beside an icon keeps its own place; a lone label is as wide as the button
          if(!withIcon){rect.x=item.x+4;rect.w=item.w-8;}else{rect.x=rect.x-2;rect.w=rect.w+4;}
          rect.h=Math.max(rect.h,18);
          if(centered){rect.h=Math.min(item.h,Math.max(24,rect.h));rect.y=Math.round(item.y+(item.h-rect.h)/2);}
        }
        item.labels.push({...rect,...textStyle(child),text:child.innerText,z:order.indexOf(child),centered});
      });
      if(k==='key'&&!item.labels.length&&el.childNodes[0]&&el.childNodes[0].nodeType===Node.TEXT_NODE&&el.childNodes[0].textContent.trim())
        item.labels.push({...geometry(el),...textStyle(el),align:'c',text:el.childNodes[0].textContent.trim(),z:order.indexOf(el)+0.1});
      if(k==='hit'&&el.parentElement.classList.contains('tabs')){
        const tabs=[...el.parentElement.querySelectorAll(':scope > .tab')],hits=[...el.parentElement.querySelectorAll(':scope > .hit')],tab=tabs[hits.indexOf(el)];
        if(tab&&tab.innerText.trim())item.labels.push({...geometry(el),...textStyle(tab),align:'c',text:tab.innerText,z:order.indexOf(el)+0.1});
      }
      widgets.push(item);
    });
    order.forEach(el=>{
      if(el.closest('.grid-ov,.guide')||el.closest('svg'))return;
      const rect=geometry(el);if(!rect.w||!rect.h)return;
      const cs=getComputedStyle(el),bg=rgb(cs.backgroundColor),owner=el.closest('[data-w]');
      if(el.classList.contains('spin'))prims.push({...rect,z:order.indexOf(el),prim:'fill',name:null,bg:[23,23,26],radius:rect.w/2,cls:'spin',owner:null,matte:matte(el)});
      else if(el.classList.contains('ico'))prims.push({...rect,z:order.indexOf(el),prim:'icon',icon:el.dataset.ico,color:rgb(cs.color),matte:matte(el),owner:owner&&name(owner)});
      else if(bg&&!el.classList.contains('t'))prims.push({...rect,z:order.indexOf(el),prim:'fill',name:name(el),bg,radius:parseFloat(cs.borderTopLeftRadius)||0,cls:el.className,owner:owner&&name(owner)});
      if(el.classList.contains('t')&&!el.dataset.w&&!(owner&&owner!==el))decor.push({...rect,...textStyle(el),text:el.innerText,z:order.indexOf(el),name:'decor_'+order.indexOf(el)});
    });
    return {id:sc.id,page:scr.dataset.page,old:scr.dataset.old,variant:vid,bg:rgb(getComputedStyle(scr).backgroundColor),widgets,prims,decor};
  }
  for(const sc of SCREENS){
    for(const vid of sc.variants?sc.variants.map(v=>v.id):['']){
      const english=capture(sc,vid,2);
      english.languages={};
      for(let li=0;li<13;li++){
        const view=li===2?english:capture(sc,vid,li);
        english.languages[li]={widgets:view.widgets.map(w=>({name:w.name,text:w.text,labels:w.labels,role:w.role,used:w.used})),decor:view.decor};
      }
      out.push(english);
    }
  }
  host.remove(); const pre=document.createElement('pre');pre.id='spec';pre.textContent=JSON.stringify(out);document.body.appendChild(pre);
}
