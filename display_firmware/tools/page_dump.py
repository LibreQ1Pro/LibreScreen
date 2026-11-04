"""Compact listing of pages of the project, to read a page without opening the editor.

    python3 display_firmware/tools/page_dump.py 15 17-20 ...      (page ids: the position in project.json)

One line per component: id, name, type, rectangle, texts (the English one set by codesload as EN=), pictures, and
the event code (a button that only sends the frame `65 <page> <action>` is shown as ACT <action>, with the name of the
constant in librescreen/screen/pageids.py when there is one).
"""
import json
import os
import re
import sys

R = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')) + '/'
ui=open(R+'librescreen/screen/pageids.py').read()
consts={m.group(1):int(m.group(2),0) for m in re.finditer(r'^(TJC_PAGE_\w+)\s*=\s*(0x[0-9a-fA-F]+|\d+)',ui,re.M)}
pj=json.load(open(R+'display_firmware/project.json')); keys=[p['key'] for p in pj['pages']]
def k(v): return v['$ref'].split(':',1)[1] if isinstance(v,dict) else v
def en_texts(d):
    out={}
    L=d['root']['events'].get('codesload',[])
    for i,l in enumerate(L):
        m=re.match(r'\s*(\w+)\.txt="(.*)"',l)
        if m: out.setdefault(m.group(1),[]).append((i,m.group(2)))
    # pick lang==2 block (English) -> index of 'lang==2' line
    sel={}
    start=None
    for i,l in enumerate(L):
        if re.search(r'lang==2\b',l): start=i
    for n,v in out.items():
        sel[n]=[t for i,t in v if start is not None and start<i<start+40][:1] or [v[0][1]]
    return {n:s[0] for n,s in sel.items()}
def show(i):
    key=keys[i]; d=json.load(open(R+'display_firmware/pages/%s.json'%key))
    en=en_texts(d)
    pref=[c for c in consts if consts[c]==i and any(o.startswith(c+'_') for o in consts)]
    sub={v:n for n,v in consts.items() if any(n.startswith(p+'_') for p in pref)}
    print('#### %d %s  bg=%s  consts=%s'%(i,key,k(d['root']['attributes'].get('pic')),pref))
    for n,l in en.items(): pass
    for j,o in enumerate(d['objects'],1):
        a=o['attributes']; n=a['objname']
        ev=[]
        for en_,lines in o['events'].items():
            if not lines: continue
            pr=[l for l in lines if l.startswith('prints ')]
            if en_=='codesup' and len(pr)>=3 and pr[1]=='prints dp,1' and pr[0]=='prints 0x65,1' and all(l.startswith('prints') or l.startswith('sys') for l in lines):
                m=re.match(r'prints (0x[0-9a-f]+|\d+),1',pr[2]); 
                try: v=int(m.group(1),0)
                except: v=None
                ev.append('ACT %s%s'%(m.group(1), ('='+sub[v]) if v in sub else ''))
            else:
                s=' | '.join(l.strip() for l in lines)
                ev.append('%s: %s'%(en_[5:],s[:150]))
        pics=[ '%s=%s'%(x,k(a[x])) for x in ('pic','picc','pic2','picc2') if x in a and a[x] not in (65535,None)]
        txt=a.get('txt','')
        t=('txt=%r'%txt[:24]) if txt else ''
        if n in en: t+=' EN=%r'%en[n][:40]
        print('%2d %-13s %-9s %3s,%3s %3sx%-3s %s %s %s'%(j,n,o['type'][:9],a.get('x',''),a.get('y',''),a.get('w',''),a.get('h',''),t,' '.join(pics)[:70],' ; '.join(ev)[:230]))
    for ev_,lines in d['root']['events'].items():
        if ev_!='codesload' and lines: print('  ROOT',ev_,' | '.join(lines)[:200])
    cl=[l for l in d['root']['events'].get('codesload',[]) if not re.search(r'\.txt=',l) and l.strip() not in('{','}') and not l.startswith('if(lang') and not l.startswith('}else')]
    if cl: print('  LOAD',' | '.join(x.strip() for x in cl)[:300])
for a in sys.argv[1:]:
    if '-' in a:
        lo,hi=map(int,a.split('-'))
        for i in range(lo,hi+1): show(i)
    else: show(int(a))
