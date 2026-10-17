import json,glob,os,datetime as dt,zoneinfo,pandas as pd,collections
RIGA=zoneinfo.ZoneInfo('Europe/Riga'); DATA=os.path.expanduser('~/mnt/Work/Trading System/_bt/_data/')
def sim(H,L,C,e,s,sd,k,bf):
    R=abs(e-s); tp=e+sd*k*R; tr=e+sd*bf*k*R; st=s; moved=False
    for i in range(len(H)):
        if (L[i]<=st) if sd==1 else (H[i]>=st): return (0.0 if moved else -1.0)
        if (H[i]>=tp) if sd==1 else (L[i]<=tp): return float(k)
        if not moved and ((H[i]>=tr) if sd==1 else (L[i]<=tr)): moved=True; st=e
    return float((C[-1]-e)*sd/R)
D={}
def load(s):
    if s not in D:
        d=pd.read_csv(DATA+'%s_5y_M5.csv.gz'%s,parse_dates=['timestamp']).set_index('timestamp'); D[s]=d[~d.index.duplicated()].sort_index()
    return D[s]
def be80(T):
    out=[]
    for x in T:
        d=load(x['sym']); day=dt.date.fromisoformat(x['day']); hh,mm=map(int,x['t'].split(':'))
        t=pd.Timestamp(dt.datetime(day.year,day.month,day.day,hh,mm,tzinfo=RIGA).astimezone(dt.timezone.utc))
        end=pd.Timestamp(dt.datetime(day.year,day.month,day.day,22,0,tzinfo=RIGA).astimezone(dt.timezone.utc))
        a=d[(d.index>=t)&(d.index<end)]
        if len(a)<3: R8=x['R']
        else: R8=sim(a.High.values,a.Low.values,a.Close.values,x['entry'],x['stop'],x['sd'],2,0.8)
        k='TP' if R8>1.95 else 'SL' if R8<-0.99 else 'BE' if abs(R8)<0.01 else 'EOD'
        out.append(dict(sym=x['sym'],day=x['day'],t=x['t'],R=R8,k=k))
    return out
def stats(tr):
    tr=sorted(tr,key=lambda r:(r['day'],r['t'],r['sym']))
    n=len(tr); tp=sum(r['k']=='TP' for r in tr); be=sum(r['k']=='BE' for r in tr); sl=sum(r['k']=='SL' for r in tr); eod=n-tp-be-sl
    c=pk=dd=0; sr=ms=0
    for r in tr:
        c+=r['R']; pk=max(pk,c); dd=min(dd,c-pk)
        if r['R']<-0.5: sr+=1; ms=max(ms,sr)
        else: sr=0
    return dict(n=n,tp=tp,be=be,sl=sl,eod=eod,wr=round(100*tp/max(1,n),1),wr2=round(100*(tp+be)/max(1,n),1),R=round(sum(r['R'] for r in tr),1),dd=round(dd,1),streak=ms)
def loadg(d,syms=None):
    T=[]
    for f in glob.glob(os.path.expanduser('~/%s/*.json'%d)): T+=json.load(open(f))
    return [x for x in T if x['day']<='2026-09-28' and (syms is None or x['sym'] in syms)]
if __name__=='__main__':
    seven=['EURUSD','GBPUSD','GER40','NAS100','US30','US500','XAUUSD']; new=['AUDUSD','USDJPY','XAGUSD']
    old=json.load(open(os.path.expanduser('~/mnt/Work/Trading System/_тесты_2026-10/скрипты_2026-10-16/w23/pn_be80.json')))
    print('pn_be80 (7 инстр, аналитика):',stats(old))
    N=be80(loadg('pn_v394',new)); json.dump(N,open(os.path.expanduser('~/new3_be80.json'),'w'))
    for s in new: print(s,stats([x for x in N if x['sym']==s]))
    print('3 новых:',stats(N)); allT=old+N; print('10 инстр:',stats(allT))
    for y in range(2021,2027):
        a=[x for x in old if x['day'][:4]==str(y)]; b=[x for x in allT if x['day'][:4]==str(y)]
        print(y,'7:',stats(a) if a else '-','| 10:',stats(b) if b else '-')
