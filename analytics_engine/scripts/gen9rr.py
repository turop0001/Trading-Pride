import sys,os,json,datetime as dt,pandas as pd,numpy as np,zoneinfo,importlib.util
sys.path.insert(0,os.getcwd())
sp=importlib.util.spec_from_file_location('pult_s1',os.path.expanduser(os.environ.get('S1FILE','~/vs2.py'))); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m); sys.modules['pult_s1']=m
import pult_rules as pr, pult_ctx as cx
RIGA=zoneinfo.ZoneInfo('Europe/Riga')
def offof(day): return int(dt.datetime.combine(day,dt.time(12,0),RIGA).utcoffset().total_seconds()//3600)
RRS=(1.5,2.0,2.5,3.0)
def simk(H,L,C,e,s,sd,k):
    R=abs(e-s); tp=e+sd*k*R
    for i in range(len(H)):
        if (L[i]<=s) if sd==1 else (H[i]>=s): return -1.0
        if (H[i]>=tp) if sd==1 else (L[i]<=tp): return k
    return float((C[-1]-e)*sd/R) if len(C) else 0.0
def simbe(H,L,C,e,s,sd,k,frac=0.9):
    R=abs(e-s); tp=e+sd*k*R; trig=e+sd*frac*k*R; st=s; moved=False
    for i in range(len(H)):
        if (L[i]<=st) if sd==1 else (H[i]>=st): return (0.0 if moved else -1.0)
        if (H[i]>=tp) if sd==1 else (L[i]<=tp): return k
        if not moved and ((H[i]>=trig) if sd==1 else (L[i]<=trig)): moved=True; st=e
    return float((C[-1]-e)*sd/R) if len(C) else 0.0
def work(a):
    sym,yr=a; yr=int(yr)
    if os.path.exists(os.path.expanduser('~/'+os.environ.get('OUTD','g9')+'/g9_%s_%d.json'%(sym,yr))): return sym,yr,'skip'
    for k in ('MD','XD','XR','ND','VB','VDOJI','ML','VAR','TR','NB','LQ','LQD','ST','FV'): os.environ.pop(k,None)
    os.environ.update(VB='7',VDOJI='1',ML='0.5',VAR=os.environ.get('VARX','base'))
    if os.environ.get('FVX'): os.environ['FV']=os.environ['FVX']
    d=pd.read_csv(os.path.expanduser('~/d2w/%s_5y_M5.csv.gz'%sym),parse_dates=['timestamp']).set_index('timestamp').sort_index()
    d=d[~d.index.duplicated()]
    days=sorted(set((d.index+pd.Timedelta(hours=3)).date)); out=[]
    for day in days[12:]:
        if day.weekday()>=5 or day<dt.date(2021,10,11) or day.year!=yr: continue
        off=offof(day)
        now=dt.datetime.combine(day,dt.time(14,0))-dt.timedelta(hours=off); ts=pd.Timestamp(now,tz='UTC')
        dd=d[(d.index<ts)&(d.index>=ts-pd.Timedelta(days=11))]
        if len(dd)<500: continue
        pr.LASTMETA={}
        try: r=pr.analyze(sym,dd,'A',now,off,{})
        except Exception: continue
        sig=r.get('signal')
        if not sig: continue
        sd=1 if sig['side']=='long' else -1
        end=pd.Timestamp(dt.datetime.combine(day,dt.time(22,0))-dt.timedelta(hours=off),tz='UTC')
        t=pd.Timestamp(sig['t_utc']); aft=d[(d.index>=t)&(d.index<end)]
        e,s=sig['entry'],sig['stop']
        Rk={str(k):simk(aft.High.values,aft.Low.values,aft.Close.values,e,s,sd,k) for k in RRS}
        rk=float(os.environ['RRX']); rec=dict(sym=sym,day=str(day),sd=sd,t=sig['time'],entry=e,stop=s,risk=abs(e-s),R=Rk[str(rk)],Rk=Rk,Rbe=simbe(aft.High.values,aft.Low.values,aft.Close.values,e,s,sd,rk))
        try:
            c=m.analyze_day(dd,day,off,sd)['cand']
            rec.update(g=c['g'],ge=c['ge'],start=c['start'],nsw=c['nsw'],strong=c['strong'],ret=c['ret'],sw_atr=c['sw_atr'])
        except Exception as ex: rec['err1']=str(ex)[:60]
        try:
            h=d[(d.index<t)&(d.index>=t-pd.Timedelta(days=12))].resample('1h').agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
            h=h[h.index+pd.Timedelta(hours=1)<=t]
            h1w=h[h.index>h.index[-1]-pd.Timedelta(days=7)]
            sw=cx._trend_dyn(h1w,0,1.0,False)
            hi,lo=float(sw['hi']),float(sw['lo']) if sw.get('hi') is not None and sw.get('lo') is not None else (None,None)
            rec.update(tr=int(sw['tr']),dep=float(sw['dep']) if sw.get('dep') is not None else None,deep=bool(sw.get('deep')))
            if sw.get('hi') is not None and sw.get('lo') is not None:
                hi=float(sw['hi']);lo=float(sw['lo']); rec['pos_leg']=(e-lo)/(hi-lo) if hi>lo else None; rec['hi']=hi;rec['lo']=lo
            H7=float(h1w.High.max());L7=float(h1w.Low.min()); rec['pos7']=(e-L7)/(H7-L7) if H7>L7 else None
            hh=h[h.index>h.index[-1]-pd.Timedelta(days=3)]; rec['pos3']=(e-float(hh.Low.min()))/(float(hh.High.max())-float(hh.Low.min()))
        except Exception as ex: rec['err2']=str(ex)[:80]
        out.append(rec)
    json.dump(out,open(os.path.expanduser('~/'+os.environ.get('OUTD','g9')+'/g9_%s_%d.json'%(sym,yr)),'w'))
    return sym,yr,len(out)
if __name__=='__main__':
    os.makedirs(os.path.expanduser('~/'+os.environ.get('OUTD','g9')),exist_ok=True)
    from multiprocessing import Pool
    with Pool(4) as p:
        for r in p.imap_unordered(work,[tuple(x.split(':')) for x in sys.argv[1:]]): print(r,flush=True)
