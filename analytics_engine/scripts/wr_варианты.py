import json,glob,os
def load(n):
    T=[]
    for f in glob.glob(os.path.expanduser('~/g10_%s/*.json'%n)): T+=json.load(open(f))
    return [x for x in T if x['day']<='2026-09-28']
B=load('base'); N=load('new')
def c(T):
    tp=sum(x['R']>0.05 for x in T); sl=sum(x['R']<-0.05 for x in T); be=len(T)-tp-sl; n=len(T)
    return n,tp,be,sl
def show(name,T):
    n,tp,be,sl=c(T)
    print('%-26s n%4d TP%4d БУ%3d SL%4d | WR1 TP/все %.1f%% | WR2 (TP+БУ)/все %.1f%% | WR3 TP/(TP+SL) %.1f%%'%(name,n,tp,be,sl,100*tp/n,100*(tp+be)/n,100*tp/(tp+sl)))
show('7 инструментов',B)
for s in ['AUDUSD','USDJPY','XAGUSD']: show(s,[x for x in N if x['sym']==s])
show('+3 новых',[x for x in N if x['sym'] in('AUDUSD','USDJPY','XAGUSD')])
show('10 инструментов',B+[x for x in N if x['sym'] in('AUDUSD','USDJPY','XAGUSD')])
