# БУ 80% для 394 сделок Типа A (pn_final, до 28.09.2026): R после переноса стопа на вход при 80% пути к цели 2R.
import json,glob,os,sys,datetime as dt,zoneinfo,pandas as pd
sys.path.insert(0,'.'); 
BASE=os.path.expanduser('~/mnt/Trading System'); DATA=BASE+'/_bt/_data'; RIGA=zoneinfo.ZoneInfo('Europe/Riga')
T=[]
for f in glob.glob(os.path.expanduser('~/an17/pn_final/*.json')): T+=json.load(open(f))
T=sorted([x for x in T if x['day']<='2026-09-28'],key=lambda x:(x['day'],x['t'],x['sym']))
D={}
def load(s):
    if s in D: return D[s]
    d=pd.read_csv(DATA+'/%s_5y_M5.csv.gz'%s,parse_dates=['timestamp']).set_index('timestamp'); d=d[~d.index.duplicated()].sort_index(); D[s]=d; return d
def sim(H,L,C,e,s,sd,k,bf):
    R=abs(e-s); tp=e+sd*k*R; tr=e+sd*bf*k*R; st=s; moved=False
    for i in range(len(H)):
        if (L[i]<=st) if sd==1 else (H[i]>=st): return (0.0 if moved else -1.0)
        if (H[i]>=tp) if sd==1 else (L[i]<=tp): return float(k)
        if not moved and ((H[i]>=tr) if sd==1 else (L[i]<=tr)): moved=True; st=e
    return float((C[-1]-e)*sd/R)
out=[];nodata=0;mism=0
for x in T:
    d=load(x['sym']); day=dt.date.fromisoformat(x['day']); hh,mm=map(int,x['t'].split(':'))
    t=pd.Timestamp(dt.datetime(day.year,day.month,day.day,hh,mm,tzinfo=RIGA).astimezone(dt.timezone.utc))
    end=pd.Timestamp(dt.datetime(day.year,day.month,day.day,22,0,tzinfo=RIGA).astimezone(dt.timezone.utc))
    a=d[(d.index>=t)&(d.index<end)]; R0=x['R']
    if len(a)<3: nodata+=1; R8=R0
    else:
        H,L,C=a.High.values,a.Low.values,a.Close.values
        r0=sim(H,L,C,x['entry'],x['stop'],x['sd'],2,1.01)   # без БУ (порог недостижим)
        if abs(r0-R0)>0.05: mism+=1
        R8=sim(H,L,C,x['entry'],x['stop'],x['sd'],2,0.8)
    k='TP' if R8>1.95 else 'SL' if R8<-0.99 else 'BE' if abs(R8)<0.01 else 'EOD'
    out.append(dict(sym=x['sym'],day=x['day'],t=x['t'],sd=x['sd'],R=R8,R0=R0,k=k,typ='A'))
json.dump(out,open('pn_be80.json','w'))
print(len(out),'нет данных',nodata,'не совпало базовое',mism,'ΣR0',round(sum(o['R0'] for o in out),1),'ΣR80',round(sum(o['R'] for o in out),1))
import collections; print(collections.Counter(o['k'] for o in out))
