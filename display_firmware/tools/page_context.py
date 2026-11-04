#!/usr/bin/env python3
"""The text of every page next to the buttons it really has: to check that an instruction mentions only what is on the screen.

    python3 tools/page_context.py > context.txt      (run from display_firmware/)

Per page: the background, the texts (the editor text = English) and the buttons that have a label or send an action
(``B name 'label' ACTION picture``); a button without a label is an icon (arrows, + / -). A text that says "tap Next"
needs a button labelled Next, or an icon button written as "›" / "+" in quotes.
"""
import json,os,re,sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import english_copy as e
import os
R=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))+'/'
ui=open(R+'librescreen/screen/pageids.py').read()
consts={m.group(1):int(m.group(2),0) for m in re.finditer(r'^(TJC_PAGE_\w+)\s*=\s*(0x[0-9a-fA-F]+|\d+)',ui,re.M)}
pj=json.load(open('project.json')); keys=[p['key'] for p in pj['pages']]
pages=sorted({p for p,_ in e.COPY}|{p for p,_ in e.BUTTON_COPY}, key=keys.index)
def ref(v): return v['$ref'].split(':')[-1] if isinstance(v,dict) else ''
for pg in pages:
    d=json.load(open('pages/%s.json'%pg)); i=keys.index(pg)
    pref=[c for c in consts if consts[c]==i and any(o.startswith(c+'_') for o in consts)]
    sub={v:n for n,v in consts.items() if any(n.startswith(p+'_') for p in pref)}
    print('##',pg,'bg=%s'%ref(d['root']['attributes'].get('pic')))
    for o in d['objects']:
        a=o['attributes']
        if o['type']=='text' and a.get('txt') and not a['txt'].startswith(('00h','XXX')):
            print('   T %-12s %s'%(o['key'],a['txt'].replace('\r\n',' ')))
    for o in d['objects']:
        if o['type']!='button' or o['key'].startswith('key_'): continue
        a=o['attributes']; ev=o['events'].get('codesup',[])
        pr=[l for l in ev if l.startswith('prints ')]; act=''
        if len(pr)>=3 and pr[1]=='prints dp,1':
            m=re.match(r'prints (0x[0-9a-f]+|\d+),1',pr[2])
            if m:
                v=int(m.group(1),0); act=sub.get(v,str(v)).replace('TJC_PAGE_','')
        if a.get('txt') or (act and not o['key'].startswith(('nav_','back_btn'))):
            print('   B %-12s %-22s %-34s %s'%(o['key'],repr(a.get('txt','')),act,ref(a.get('picc2'))))
