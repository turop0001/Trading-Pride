import json,glob,os,sys
sys.path.insert(0,os.path.expanduser('~'))
from an10 import *
import datetime as dt
def loadd(path,syms):
    T=[]
    for f in glob.glob(os.path.expanduser(path+'/*.json')):
        T+=json.load(open(f))
    return [x for x in T if x['sym'] in syms and x['day']<='2026-09-28']
base=['EURUSD','GBPUSD','GER40','NAS100','US30','US500','XAUUSD']
T=loadd('~/an17/pn_final',base)+loadd('~/pn_v394',['AUDUSD','USDJPY'])
print(len(T))
def run(T,k,bf):
    out=[]
    for x in T:
        d=load(x['sym']); day=dt.date.fromisoformat(x['day']); hh,mm=map(int,x['t'].split(':'))
        t=pd.Timestamp(dt.datetime(day.year,day.month,day.day,hh,mm,tzinfo=RIGA).astimezone(dt.timezone.utc))
        end=pd.Timestamp(dt.datetime(day.year,day.month,day.day,22,0,tzinfo=RIGA).astimezone(dt.timezone.utc))
        a=d[(d.index>=t)&(d.index<end)]
        R8=sim(a.High.values,a.Low.values,a.Close.values,x['entry'],x['stop'],x['sd'],k,bf) if len(a)>=3 else x['R']
        out.append(dict(sym=x['sym'],day=x['day'],t=x['t'],R=R8,k='TP' if R8>k-0.05 else 'SL' if R8<-0.99 else 'BE' if abs(R8)<0.01 else 'EOD',ret=x.get('ret'),dep=x.get('dep')))
    return out
if __name__=='__main__':
    res={}
    for k in (1.5,2.0,2.5,3.0):
        for bf in (0.5,0.6,0.7,0.8,0.9,1.01):
            o=run(T,k,bf); s=stats(o); res['%s_%s'%(k,bf)]=o
            print(k,bf,s['n'],'WR',s['wr'],'R',s['R'],'DD',s['dd'],'st',s['streak'],'R/DD',round(s['R']/abs(s['dd']),0),flush=True)
    json.dump(res,open('r1_res.json','w'))
