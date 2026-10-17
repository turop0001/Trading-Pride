import json,re,sys,os
H=os.path.expanduser('~'); P=H+'/pushclone/web/private/pult.html'
A=json.load(open('pn_be80.json')); TC=json.load(open('TC.json'))
def st(L):
    L=sorted(L,key=lambda x:(x['day'],x['t']));n=len(L)
    if not n: return None
    tp=sum(x['R']>0.05 for x in L);sl=sum(x['R']<-0.05 for x in L);be=n-tp-sl
    eq=pk=dd=0;s=ms=0
    for x in L:
        eq+=x['R'];pk=max(pk,eq);dd=max(dd,pk-eq);s=s+1 if x['R']<-0.05 else 0;ms=max(ms,s)
    return dict(n=n,tp=tp,sl=sl,be=be,R=eq,dd=dd,st=ms)
MR=['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
def num(v): 
    v=round(v+0.0,1); return ('%d'%abs(v)) if v==int(v) else '%.1f'%abs(v)
def fmtR(v): v=round(v+0.0,1); return ('−' if v<0 else '+' if v>0 else '')+num(v)+'R'
def tokens(a): return [str(a['n']),'%d / %d / %d'%(a['tp'],a['sl'],a['be']),fmtR(a['R']),('−'+num(a['dd'])+'R') if a['dd'] else '0R']
s=open(P,encoding='utf8').read(); line=[l for l in s.split('\n') if 'Прогон Пульта на истории' in l][0]
cards=[(m.start(),re.sub('<.*?>','',m.group(1))) for m in re.finditer(r'<div class="card"><h2>(.*?)</h2>',line)]+[(len(line),'END')]
bad=0
def sel(L,f): return [x for x in L if f(x)]
for k in range(len(cards)-1):
    title=cards[k][1]; body=line[cards[k][0]:cards[k+1][0]]
    typ=('AC' if 'A + Тип C' in title else 'A' if title.startswith('Тип A') else 'C' if 'Тип C' in title else None)
    if typ is None: continue
    base={'A':A,'C':TC,'AC':A+TC}[typ]
    nrow=0
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>',body,flags=re.S):
        cells=[re.sub('<.*?>','',c).strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>',tr,flags=re.S)]
        if not cells or cells[0] in('Набор','Год','Месяц','Инструмент'): continue
        lab=cells[0]; sub=None
        m=re.match(r'(\d{4})',lab); mm=re.match(r'([А-Яа-я]{3})[а-я]* (\d{4})',lab)
        if mm and mm.group(1).lower() in MR:
            ym='%s-%02d'%(mm.group(2),MR.index(mm.group(1).lower())+1); sub=sel(base,lambda x:x['day'][:7]==ym)
        elif m and ('с 11.10' in lab or re.fullmatch(r'\d{4}( \(.*\))?',lab)): sub=sel(base,lambda x:x['day'][:4]==m.group(1))
        elif lab in ('EURUSD','GBPUSD','GER40','NAS100','US30','US500','XAUUSD','AUDUSD'): sub=sel(base,lambda x:x['sym']==lab)
        if sub is None: continue
        a=st(sub); nrow+=1
        if a is None: continue
        row=' | '.join(cells)
        vals=[]
        for c in cells:
            mm_=re.fullmatch(r'([+−-]?)(\d+(?:\.\d+)?)R',c)
            if mm_: vals.append((-1 if mm_.group(1) in('−','-') else 1)*float(mm_.group(2)))
        miss=[]
        if str(a['n']) not in cells: miss.append('n=%d'%a['n'])
        if any(re.fullmatch(r'\d+ / \d+ / \d+',c) for c in cells) and ('%d / %d / %d'%(a['tp'],a['sl'],a['be'])) not in cells and not (str(a['tp']) in cells and str(a['sl']) in cells and str(a['be']) in cells): miss.append('TP/SL/БУ')
        if not any(abs(v-round(a['R'],1))<0.06 for v in vals): miss.append('ΣR=%.1f'%a['R'])
        has_dd=any(v<0 and abs(v)<=20 for v in vals)
        negs=[v for v in vals if v<0 or (v==0 and any(c=='0R' for c in cells))]
        if has_dd or any(c=='0R' for c in cells):
            ok_dd=any(abs(abs(v)-round(a['dd'],1))<0.06 for v in vals if v<=0 and abs(v)<=20) or (a['dd']<0.05 and '0R' in cells)
            if not ok_dd: miss.append('DD=%.1f'%a['dd'])
        if len(cells)>0 and typ in('A','AC') and any(re.fullmatch(r'\d+',c) for c in cells[-1:]) and cells[-1].isdigit() and ('Серия' in title or True):
            pass
        if miss: bad+=1; print('[%s] %s: нет %s | в строке: %s'%(title[:40],lab,miss,row[:110]))
    print('карточка',title[:60],'строк проверено',nrow)
print('расхождений',bad)
