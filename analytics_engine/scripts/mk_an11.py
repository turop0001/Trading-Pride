# Аналитика Типа A в pult.html с БУ 80% (16.10.2026). Вход: pn_be80.json (A, R с БУ 80%), TC.json (C). Меняет блоки Типа A и A+C в строке «Прогон Пульта на истории».
import json,os,re,subprocess,sys
H=os.path.expanduser('~'); PULT=sys.argv[1] if len(sys.argv)>1 else H+'/mnt/Work/Trading-Pride-Pult/web/private/pult.html'
A=sorted(json.load(open('pn_be80.json')),key=lambda x:(x['day'],x['t'],x['sym']))
TC=json.load(open('TC.json'))
def st(L):
    L=sorted(L,key=lambda x:(x['day'],x['t']));n=len(L)
    if not n: return dict(n=0,tp=0,sl=0,be=0,wr=0,R=0,avg=0,dd=0,st=0)
    tp=sum(1 for x in L if x['R']>0.05);sl=sum(1 for x in L if x['R']<-0.05);be=n-tp-sl
    eq=pk=dd=0;s=ms=0
    for x in L:
        eq+=x['R'];pk=max(pk,eq);dd=max(dd,pk-eq)
        s=s+1 if x['R']<-0.05 else 0;ms=max(ms,s)
    return dict(n=n,tp=tp,sl=sl,be=be,wr=round(100*tp/n,1),R=round(eq,1),avg=round(eq/n,2),dd=round(dd,1),st=ms)
out={}
for nm,L in (('A',A),('C',TC),('AC',A+TC)):
    out[nm]=dict(all=st(L),y26=st([x for x in L if x['day']>='2026']),
        years={y:st([x for x in L if x['day'][:4]==str(y)]) for y in range(2021,2027)},
        months={m:st([x for x in L if x['day'][:7]==m]) for m in sorted(set(x['day'][:7] for x in L))},
        syms={s:st([x for x in L if x['sym']==s]) for s in sorted(set(x['sym'] for x in L))})
json.dump(out,open('agg.json','w'),ensure_ascii=False,indent=0)
subprocess.run([sys.executable,'build_an.py'],check=True,capture_output=True)
AA=out['A']; AC=out['AC']
MINUS='−'
def fr(v,sign=True):
    v=round(v+0.0,1); s=str(int(abs(v))) if v==int(v) else '%.1f'%abs(v)
    return (MINUS if v<0 else ('+' if sign and v>0 else ''))+s+'R'
def cls(v): return 'pos' if round(v,1)>0 else ('neg' if round(v,1)<0 else '')
def fdd(dd): return fr(-dd,False) if round(dd,1)!=0 else '0R'
def ddp(dd,k): return '%s%d%%'%(MINUS if dd>0 else '',round(abs(dd)*k))
s=open(PULT,encoding='utf8').read(); lines=s.split('\n')
idx=[i for i,l in enumerate(lines) if 'Прогон Пульта на истории' in l][0]; L=lines[idx]
def card(L,title):
    a=L.index('<div class="card"><h2>'+title); b=L.find('<div class="card">',a+10); b=len(L) if b<0 else b; return a,b
def sumrow(name,a,months):
    return ('<tr><td>%s</td><td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td><td class="%s">%s</td><td>%s</td><td>%.1f</td><td>%s</td><td>%s</td><td>%s / %s</td></tr>'
        %(name,a['n'],a['tp'],a['sl'],a['be'],a['wr'],cls(a['R']),fr(a['R']),fr(a['avg']),a['n']/months,fr(a['R']/months),fdd(a['dd']),ddp(a['dd'],0.25),ddp(a['dd'],1)))
def acrow(name,a,months):
    return ('<tr class="tot"><td>%s</td><td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td><td class="%s">%s</td><td>%s</td><td>%.1f</td><td>%s</td><td>%s</td><td>%s / %s</td></tr>'
      %(name,a['n'],a['tp'],a['sl'],a['be'],a['wr'],cls(a['R']),fr(a['R']),fr(a['avg']),a['n']/months,fr(a['R']/months),fdd(a['dd']),ddp(a['dd'],0.25),ddp(a['dd'],1)))
i0=L.index('<tr><td>Тип A · 9 инстр. · 2026'); i1=L.index('<tr class="tot"><td>Тип C · 3 инстр. · 2026</td>')
L=L[:i0]+sumrow('Тип A · 11 инстр. · 2026 (БУ 80%)',AA['y26'],9)+sumrow('Тип A · 11 инстр. · 5 лет (БУ 80%)',AA['all'],60)+L[i1:]
j0=L.index('<tr class="tot"><td>Тип A + Тип C вместе · 2026</td>'); j1=L.index('</tbody>',j0)
L=L[:j0]+acrow('Тип A + Тип C вместе · 2026',AC['y26'],9)+acrow('Тип A + Тип C вместе · 5 лет',AC['all'],59.8)+L[j1:]
m=re.search(r'Макс\. серия SL подряд: Тип A \d+ \(5 лет\) / \d+ \(2026\), Тип C 6 / 5, вместе \d+ / \d+',L)
L=L.replace(m.group(0),'Макс. серия SL подряд: Тип A %d (5 лет) / %d (2026), Тип C 6 / 5, вместе %d / %d'%(AA['all']['st'],AA['y26']['st'],AC['all']['st'],AC['y26']['st']))
def r_i(name,a,tot=False):
    return ('<tr%s><td>%s</td><td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td><td class="%s">%s</td><td>%s</td><td>%s</td><td>%d</td></tr>'
      %(' class="tot"' if tot else '',name,a['n'],a['tp'],a['sl'],a['be'],a['wr'],cls(a['R']),fr(a['R']),fr(a['avg']),fdd(a['dd']),a['st']))
a5=AA['all'];a6=AA['y26']
blk2=('<div class="card"><h2>Тип A · итоги по правилам Пульта на 16.10.2026</h2><p class="note">Прогон правил Пульта на истории Dukascopy M5, 11 инструментов. Без спреда и комиссий, вход по открытию свечи после триггера, цель 2R, БУ на 80%% пути к цели (стоп переносится на вход, сделка закрывается в 0R). Фильтр с 16.10.2026: п.5 — вынос к моменту сигнала не меньше 1,93 ATR (иначе скип дня), окно входа 10:00–13:00 (свеча входа открывается до 13:00); триггер — ≥3 сильные свечи выкупа ИЛИ откат ≥30%%. Период «5 лет» — 11.10.2021 – 28.09.2026, «2026» — 01.01 – 28.09.2026.</p>'
 '<div class="kpis"><div class="kpi"><small>Сделок · 5 лет</small><b class="">%d</b></div><div class="kpi"><small>WR</small><b class="">%.1f%%</b></div><div class="kpi"><small>ΣR · 5 лет</small><b class="%s">%s</b></div><div class="kpi"><small>R / сделка</small><b class="">%s</b></div><div class="kpi"><small>Макс. просадка</small><b class="neg">%s</b></div><div class="kpi"><small>Макс. серия SL</small><b class="">%d</b></div></div>'
 %(a5['n'],a5['wr'],cls(a5['R']),fr(a5['R']),fr(a5['avg']),fdd(a5['dd']),a5['st'])
 +'<div class="tw"><table><thead><tr><th>Набор</th><th>Сделок</th><th>TP / SL / БУ</th><th>WR</th><th>ΣR</th><th>R / сделка</th><th>Макс. просадка</th><th>Макс. серия SL</th></tr></thead><tbody>'
 +r_i('5 лет · ПРАВИЛА С 16.10 + БУ 80%',a5,True)+r_i('2026 · ПРАВИЛА С 16.10 + БУ 80%',a6,True)+'</tbody></table></div></div>')
a,b=card(L,'Тип A · итоги по правилам'); L=L[:a]+blk2+L[b:]
comb=open('comb_card.html',encoding='utf8').read()
comb=re.sub(r'<p class="note">.*?</p>','<p class="note">Оба типа по правилам Пульта: Тип A — с 16.10.2026 (вынос ≥1,93 ATR, вход до 13:00, цель 2R, БУ 80%); Тип C — откат 20%, цель 3R, БУ 50%. 11 инструментов для A и 3 для C, сделки сложены по датам. Просадка — от пика общей кривой ΣR внутри периода.</p>',comb,count=1,flags=re.S)
a,b=card(L,'Тип A + Тип C вместе'); L=L[:a]+comb+L[b:]
syms=['EURUSD','GBPUSD','GER40','NAS100','US30','US500','XAUUSD','AUDUSD','USDJPY','UK100','EURGBP']
def cellset(a): return '<td>%d</td><td>%d%%</td><td>%d</td><td class="%s">%s</td>'%(a['n'],round(a['wr']),a['be'],cls(a['R']),fr(a['R']))
rows=''
for sy in syms:
    n5=AA['syms'][sy]; n26=st([x for x in A if x['sym']==sy and x['day']>='2026'])
    rows+='<tr><td>%s</td>%s<td>%s</td>%s</tr>'%(sy,cellset(n5),fdd(n5['dd']),cellset(n26))
rows+='<tr class="tot"><td>Итого</td>%s<td>%s</td>%s</tr>'%(cellset(a5),fdd(a5['dd']),cellset(a6))
blk3=('<div class="card"><h2>Тип A · по инструментам</h2><div class="tw"><table><thead><tr><th>Инструмент</th><th colspan="5">5 лет (с БУ 80%)</th><th colspan="4">2026 (с БУ 80%)</th></tr>'
 '<tr><th></th><th>Сделок</th><th>WR</th><th>БУ</th><th>ΣR</th><th>Просадка</th><th>Сделок</th><th>WR</th><th>БУ</th><th>ΣR</th></tr></thead><tbody>'+rows+'</tbody></table></div></div>')
a,b=card(L,'Тип A · по инструментам'); L=L[:a]+blk3+L[b:]
yr_rows=''
for y in range(2021,2027):
    t=AA['years'][y]; nm=str(y)+(' (с 11.10)' if y==2021 else '')
    yr_rows+='<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d%%</td><td class="%s">%s</td><td>%s</td><td>%s</td><td>%d</td></tr>'%(nm,t['n'],t['tp'],t['sl'],t['be'],round(t['wr']),cls(t['R']),fr(t['R']),fr(t['avg']),fdd(t['dd']),t['st'])
yr_rows+='<tr class="tot"><td>Итого</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d%%</td><td class="%s">%s</td><td>%s</td><td>%s</td><td>%d</td></tr>'%(a5['n'],a5['tp'],a5['sl'],a5['be'],round(a5['wr']),cls(a5['R']),fr(a5['R']),fr(a5['avg']),fdd(a5['dd']),a5['st'])
blk4=('<div class="card"><h2>Тип A · по годам (5 лет, с БУ 80%)</h2><div class="tw"><table><thead><tr><th>Год</th><th>Сделок</th><th>TP</th><th>SL</th><th>БУ</th><th>WR</th><th>ΣR</th><th>R / сделка</th><th>Макс. просадка</th><th>Макс. серия SL</th></tr></thead><tbody>'+yr_rows+'</tbody></table></div></div>')
a,b=card(L,'Тип A · по годам'); L=L[:a]+blk4+L[b:]
MN=['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
def mrows(months):
    o=''
    for m in months:
        t=AA['months'][m]
        o+='<tr><td>%s %s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d%%</td><td class="%s">%s</td><td>%s</td><td>%s</td><td>%d</td></tr>'%(MN[int(m[5:])-1],m[:4],t['n'],t['tp'],t['sl'],t['be'],round(t['wr']),cls(t['R']),fr(t['R']),fr(t['avg']),fdd(t['dd']),t['st'])
    return o
th='<div class="tw"><table><thead><tr><th>Месяц</th><th>Сделок</th><th>TP</th><th>SL</th><th>БУ</th><th>WR</th><th>ΣR</th><th>R / сделка</th><th>Макс. просадка</th><th>Макс. серия SL</th></tr></thead><tbody>'
def tot(t): return '<tr class="tot"><td>Итого</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d%%</td><td class="%s">%s</td><td>%s</td><td>%s</td><td>%d</td></tr>'%(t['n'],t['tp'],t['sl'],t['be'],round(t['wr']),cls(t['R']),fr(t['R']),fr(t['avg']),fdd(t['dd']),t['st'])
ms=sorted(AA['months']); m26=[m for m in ms if m[:4]=='2026']
blk5=('<div class="card"><h2>Тип A · по месяцам</h2><details><summary>2026 год по месяцам (%d)</summary>'%len(m26)+th+mrows(m26)+tot(a6)+'</tbody></table></div></details>'
 +'<details><summary>5 лет по месяцам (%d)</summary>'%len(ms)+th+mrows(ms)+tot(a5)+'</tbody></table></div></details></div>')
a,b=card(L,'Тип A · по месяцам'); L=L[:a]+blk5+L[b:]
nd5=14163-AA['all']['n'];nd6=2116-AA['y26']['n']
L=re.sub(r'Тип A 5 лет — \d+, 2026 — \d+','Тип A 5 лет — %d, 2026 — %d'%(nd5,nd6),L)
lines[idx]=L
open(PULT,'w',encoding='utf8').write('\n'.join(lines))
print('A 5л',a5,'\nA 26',a6,'\nAC',AC['all'],AC['y26'])
