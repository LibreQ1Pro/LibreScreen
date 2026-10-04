"""Proposes names for the pictures of the STOCK project from where they are used (the first use: page, component,
attribute, language of the language chains); names that were chosen by hand for the pictures the host sends by id
are in pic_manual.json. This is the script that made the picture part of names.json; it needs the stock project
(display_firmware of commit c5c653b plus tools/add_network_pages.py) and the component names of the stock.
"""
import collections
import json
import os
import re

S = os.path.dirname(os.path.abspath(__file__)) + '/'
names = json.load(open(S + 'names.json'))['pages']   # (component names are looked up in the stock project, see above)
pj=json.load(open(S+'../project.json'))
pics=[p['key'] for p in pj['pictures']]
use=collections.defaultdict(list)
def k(v): return v['$ref'].split(':',1)[1] if isinstance(v,dict) and '$ref' in v else None
for pg in pj['pages']:
    pk=pg['key']; d=json.load(open(S+'../'+pg['content']['path']))
    nm=names.get(pk,{})
    ra=d['root']['attributes']
    if k(ra.get('pic')): use[k(ra['pic'])].append((pk,'bg','pic',None))
    for o in d['objects']:
        on=nm.get(o['attributes']['objname'],o['attributes']['objname'])
        for a in ('pic','picc','pic2','picc2','pic1','picc1','bpic','ppic'):
            if k(o['attributes'].get(a)): use[k(o['attributes'][a])].append((pk,on,a,None))
    evs=list(d['root']['events'].values())+[v for o in d['objects'] for v in o['events'].values()]
    LANGS=['cn','ru','en','jp','fr','de','it','es','kr','pt','ar','tr','he']
    for lines in [d['root']['events'].get('codesload',[])]+evs:
        lang=None
        for l in lines:
            ml=re.search(r'if\(lang==(\d+)\)',l)
            if ml: lang=int(ml.group(1))
            elif l.strip()=='}else': lang=12
            for m in re.finditer(r'(\w+)\.(pic\w*)=\$\{picture:([^}]+)\}',l):
                on=nm.get(m.group(1),m.group(1)); use[m.group(3)].append((pk,on,m.group(2),LANGS[lang] if lang is not None else None))
MANUAL=json.load(open(S+'pic_manual.json'))
def auto(key):
    U=use.get(key)
    if not U: return 'unused_'+key.split('_')[1] if key.startswith('pic_') else key
    pages=[]
    for u in U:
        if u[0] not in pages: pages.append(u[0])
    if any(u[1]=='bg' for u in U):
        return 'bg_'+[u[0] for u in U if u[1]=='bg'][0]
    p0=pages[0]
    local=[u for u in U if u[0]==p0]
    first=local[0]
    role={'pic':'','picc':'','pic1':'_fg','picc1':'_fg','pic2':'_press','picc2':'_press'}.get(first[2],'')
    lang=[u[3] for u in local if u[3]]
    return p0+'_'+first[1]+role+('_'+lang[0] if lang else '')
out={}
for key in pics:
    out[key]=MANUAL.get(key) or (auto(key) if key.startswith('pic_') else key)
seen=collections.Counter()
for key in pics:
    n=out[key]; seen[n]+=1
    if seen[n]>1: out[key]=n+'_%d'%seen[n]
if __name__=='__main__':
    json.dump(out,open(S+'pic_auto.json','w'),indent=0)  # proposal; names.json has the final names
    multi=[key for key in pics if len({u[0] for u in use.get(key,[])})>1]
    print(len(out), len(set(out.values())))
    for key in multi: print(pics.index(key),key,'->',out[key],sorted({u[0] for u in use[key]})[:5])
