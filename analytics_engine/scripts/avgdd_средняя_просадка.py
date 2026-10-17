import re,json,os,sys
H=os.path.expanduser('~/w24x/')
A=json.load(open(H+'pn_be80.json'));C=json.load(open(H+'TC.json'))
for L in (A,C): L.sort(key=lambda x:(x['day'],x['t'],x['sym']))
def avgdd(tr):
    ms={}
    for x in tr: ms.setdefault(x['day'][:7],[]).append(x)
    v=[]
    for m,l in ms.items():
        eq=pk=dd=0
        for x in l:
            eq+=x['R'];pk=max(pk,eq);dd=max(dd,pk-eq)
        v.append(dd)
    return sum(v)/len(v) if v else 0
def fmt(d): return '−%.1fR'%d if d>0 else '0R'
def sub(L,label):
    y=re.match(r'(\d{4})',label)
    if label.startswith('5 лет') or 'всего' in label: return L
    if y: return [x for x in L if x['day'][:4]==y.group(1)]
    return L
def sel(tid,label):
    lab=label
    if tid=='T1':
        L = (A+C) if 'вместе' in lab else (A if 'Тип A' in lab else C)
        L=sorted(L,key=lambda x:(x['day'],x['t'],x['sym']))
        return [x for x in L if x['day']>='2026-01-01'] if '2026' in lab else L
    if tid in('T2','T7'): return sub(A,lab)
    if tid in('T3','T4'): return sub(C,lab)
    if tid=='T5': return [x for x in C if x['sym']==lab]
    if tid=='T6': return sub(sorted(A+C,key=lambda x:(x['day'],x['t'],x['sym'])),lab)
SIG={'T1':'Просадка в % (0,25% / 1%)','T2':None,'T3':None}
NEWH='Средняя просадка (по месяцам)'
def patch(s):
    out=[];pos=0;cnt=0
    for m in re.finditer(r'<table><thead><tr>((?:<th>[^<]*</th>)+)</tr></thead>',s):
        h=re.findall(r'<th>([^<]*)</th>',m.group(1))
        if NEWH in h or not any('росадк' in x for x in h) or 'Месяц' in h[0] or 'внутри' in ' '.join(h): continue
        e=s.find('</table>',m.end())
        rows=re.findall(r'<tr[^>]*>.*?</tr>',s[m.end():e])
        first=[re.sub('<[^>]+>','',re.findall(r'<td[^>]*>(.*?)</td>',r)[0]) for r in rows[1:]] if False else None
        h0=h[0]
        if h0=='Набор' and 'Макс. серия SL' not in h and h[-1].startswith('Просадка в %'): tid='T1'
        elif h0=='Набор':
            tid='T2' if 'БУ 80%' in s[m.end():e] else 'T3'
        elif h0=='Год' and 'Тип A: сделок' in h: tid='T6'
        elif h0=='Год' and 'TP' in h: tid='T7'
        elif h0=='Год': tid='T4'
        elif h0=='Инструмент': tid='T5'
        else: continue
        di=[i for i,x in enumerate(h) if 'росадк' in x][0]
        out.append((m.start(),m.end(),e,tid,di));
    for st,en,e,tid,di in reversed(out):
        seg=s[st:e]
        seg=seg.replace('</th>','</th>#',0)
        ths=re.findall(r'<th>[^<]*</th>',seg)
        seg=seg.replace(ths[di],ths[di]+'<th>%s</th>'%NEWH,1)
        def rr(mo):
            r=mo.group(0)
            if '<td' not in r: return r
            tds=re.findall(r'<td[^>]*>.*?</td>',r)
            lab=re.sub('<[^>]+>','',tds[0])
            lab=re.sub(r'\s*\(.*?\)','',lab).strip() if tid!='T1' else lab
            if tid in('T2','T3'): lab='2026' if lab.startswith('2026') else '5 лет'
            L=sel(tid,lab)
            if not L: return r
            nt='<td>%s</td>'%fmt(avgdd(L))
            return r.replace(tds[di],tds[di]+nt,1)
        seg=re.sub(r'<tr[^>]*>.*?</tr>',rr,seg)
        s=s[:st]+seg+s[e:];cnt+=1
    return s,cnt
if __name__=='__main__':
    for f in sys.argv[1:]:
        s=open(f,encoding='utf8').read();s2,c=patch(s);open(f,'w',encoding='utf8').write(s2);print(f,c)
