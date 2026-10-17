import sys,os,glob,json
sys.path.insert(0,os.path.expanduser('~'))
from r1 import *
import itertools
extra=['UK100','EURGBP','USDCAD','EU50']
X=loadd('~/pn_x',extra)
print({s:sum(1 for x in X if x['sym']==s) for s in extra})
b=run(T,2.0,0.8); json.dump(b,open('r2_base.json','w'))
ex=run(X,2.0,0.8)
for s in extra: print(s,stats([x for x in ex if x['sym']==s]))
print('base',stats(b))
for r in (1,2):
  for c in itertools.combinations(extra,r):
    print(c,stats(b+[x for x in ex if x['sym'] in c]))
