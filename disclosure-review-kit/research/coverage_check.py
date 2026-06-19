import os
import json, sys
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','lib')); import opportunity as o
tax=json.load(open(os.path.join(os.path.dirname(__file__),'asx_taxonomy.json'),encoding='utf-8'))
gran=tax['granular']
mapped=[]; unmapped=[]
for t,n in sorted(gran.items(), key=lambda x:-x[1]):
    r=o.classify_opportunity({'type':t,'headline':''})
    if r['ruleId']=='none':
        unmapped.append((t,n))
    else:
        mapped.append((t,n,r['rag'],r['ruleId'],','.join(r['services']) or '-'))
print('=== MAPPED granular types ({}/{}) ==='.format(len(mapped),len(gran)))
for t,n,rag,rid,svc in mapped:
    print(f'  {rag:5} {t[:46]:46} -> {rid} [{svc[:38]}]')
print('\n=== UNMAPPED (fall through to RED/none) — review for service fit ===')
for t,n in unmapped:
    print(f'  ({n:3})  {t}')
