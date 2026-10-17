import json,re
o=json.load(open('agg.json'))
A,C,AC=o['A'],o['C'],o['AC']
def f1(x): return ('%+.1f'%x).replace('+-','-')
def R(x): return '<td class="%s">%s%sR</td>'%('pos' if x>0 else 'neg' if x<0 else '', '+' if x>0 else '', ('%.1f'%x).rstrip('0').rstrip('.') if False else ('%.1f'%x))
def Rs(x): return '%s%.1fR'%('+' if x>0 else '−' if x<0 else '',abs(x))
def cell(x): return '<td class="%s">%s</td>'%('pos' if x>0 else 'neg' if x<0 else '',Rs(x))
def pct(d,rk): return '−%d%%'%round(d*rk/100*100) if d else '0%'
def dd(x): return '−%sR'%(('%g'%x))
MONTHS={'01':'янв','02':'фев','03':'мар','04':'апр','05':'май','06':'июн','07':'июл','08':'авг','09':'сен','10':'окт','11':'ноя','12':'дек'}
def mname(m): return MONTHS[m[5:]]+' '+m[:4]
YN={2021:'2021 (с 11.10)',2026:'2026 (до 28.09)'}
# 1. summary rows
def row(name,s,months,bold=False):
    n=s['n'];rm=s['R']/months
    cls=' class="tot"' if bold else ''
    return ('<tr%s><td>%s</td><td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td>%s<td>%+.2fR</td><td>%.1f</td><td>%+.1fR</td><td>%s</td><td>−%d%% / −%d%%</td></tr>'
        %(cls,name,n,s['tp'],s['sl'],s['be'],s['wr'],cell(s['R']),s['avg'],n/months,rm,dd(s['dd']),round(s['dd']*0.25/100*100),round(s['dd'])))
M5=59.8;M26=9.0
rows_sum=''.join([
 row('Тип C · 3 инстр. · 2026 (правила с 08.10)',C['y26'],M26,True),
 row('Тип C · 3 инстр. · 5 лет (правила с 08.10)',C['all'],M5,True),
 row('Тип A + Тип C вместе · 2026',AC['y26'],M26,True),
 row('Тип A + Тип C вместе · 5 лет',AC['all'],M5,True)])
old_c='<tr><td>Тип C · 3 инстр. · 2026 (до 08.10: поглощение / откат 30%, цель 2R)</td><td>249</td><td>115 / 88 / 46</td><td>46.2%</td><td class="pos">+134.2R</td><td>+0.54R</td><td>27.7</td><td>+14.9R</td><td>−8R</td><td>−2% / −8%</td></tr><tr><td>Тип C · 3 инстр. · 5 лет (до 08.10: поглощение / откат 30%, цель 2R)</td><td>1646</td><td>786 / 644 / 216</td><td>47.8%</td><td class="pos">+880.1R</td><td>+0.53R</td><td>27.4</td><td>+14.7R</td><td>−10R</td><td>−2% / −10%</td></tr>'
open('sum_rows.html','w').write(rows_sum+old_c)
# 2. Type C card
def tbl(head,rows): return '<div class="tw"><table><thead><tr>'+''.join('<th>%s</th>'%h for h in head)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
def kpi(l,v,c=''): return '<div class="kpi"><small>%s</small><b class="%s">%s</b></div>'%(l,c,v)
ca=C['all'];c6=C['y26']
Ccard=('<div class="card"><h2>Тип C · итоги по правилам Пульта на 08.10.2026</h2><p class="note">Прогон правил Пульта (код движка, 3 инструмента: XAUUSD, EURUSD, GBPUSD) на истории Dukascopy M5: каждый торговый день в окне 16:30–18:30 Рига; исход до 22:00. Механически: без спреда и комиссий. <b>Правила Типа C с 08.10.2026: вход всегда на откате 20% длины выноса (вход по поглощению свечи выноса отменён), стоп за экстремумом + 0,1R, цель 3R (раньше 2R), стоп в безубыток на 50% пути к цели (раньше 70%).</b> Скипы без изменений (скип №8 — встречный H1 FVG теперь внутри цели 1:3). Период «5 лет» — 11.10.2021 – 28.09.2026, «2026» — 01.01 – 28.09.2026.</p>'
 '<div class="kpis">'+kpi('Сделок · 5 лет',ca['n'])+kpi('WR','%.1f%%'%ca['wr'])+kpi('ΣR · 5 лет',Rs(ca['R']),'pos')+kpi('R / сделка','%+.2fR'%ca['avg'])+kpi('Макс. просадка',dd(ca['dd']),'neg')+kpi('Макс. серия SL',ca['st'])+'</div>'
 +tbl(['Набор','Сделок','TP / SL / БУ','WR','ΣR','R / сделка','Макс. просадка','Макс. серия SL'],[
  '<tr><td>5 лет · правила до 08.10 (поглощение / откат 30%, цель 2R, БУ 70%)</td><td>1646</td><td>786 / 644 / 216</td><td>47.8%</td><td class="pos">+880.1R</td><td>+0.53R</td><td>−10R</td><td>8</td></tr>',
  '<tr class="tot"><td>5 лет · ПРАВИЛА С 08.10 (откат 20%%, цель 3R, БУ 50%%)</td><td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td>%s<td>%+.2fR</td><td>%s</td><td>%d</td></tr>'%(ca['n'],ca['tp'],ca['sl'],ca['be'],ca['wr'],cell(ca['R']),ca['avg'],dd(ca['dd']),ca['st']),
  '<tr><td>2026 · правила до 08.10</td><td>249</td><td>115 / 88 / 46</td><td>46.2%</td><td class="pos">+134.2R</td><td>+0.54R</td><td>−8R</td><td>8</td></tr>',
  '<tr class="tot"><td>2026 · ПРАВИЛА С 08.10</td><td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td>%s<td>%+.2fR</td><td>%s</td><td>%d</td></tr>'%(c6['n'],c6['tp'],c6['sl'],c6['be'],c6['wr'],cell(c6['R']),c6['avg'],dd(c6['dd']),c6['st'])])
 +'<p class="note" style="margin-top:10px">Как читать: новые правила дают за 5 лет +1601.7R вместо +880.1R при просадке −7R вместо −10R и серии SL 6 вместо 8; WR ниже (43.7% против 47.8%), потому что цель дальше (3R), но каждая сделка в среднем приносит +0.94R вместо +0.53R; БУ срабатывает чаще (на 50% пути). Сделок больше (1695 против 1646): входы по поглощению заменены входами на откате 20%. Сравнение «до» взято из прежней сводки Аналитики; на тех же данных повторный прогон старых правил даёт 1560 сделок / +841.6R (расхождение ~5% не объяснено), прирост от новых правил в прогоне +760R. Параметры подобраны на тех же 5 годах и без спреда — живой результат будет скромнее; микростопы особенно чувствительны к спреду.</p>'
 +'<h3 style="margin:14px 0 6px;font-size:15px">По годам (правила с 08.10)</h3>'
 +tbl(['Год','Сделок','TP / SL / БУ','WR','ΣR','R / сделка','Макс. просадка','Макс. серия SL'],[
   '<tr><td>%s</td><td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td>%s<td>%+.2fR</td><td>%s</td><td>%d</td></tr>'%(YN.get(int(y),y),s['n'],s['tp'],s['sl'],s['be'],s['wr'],cell(s['R']),s['avg'],dd(s['dd']),s['st']) for y,s in C['years'].items()])
 +'<h3 style="margin:14px 0 6px;font-size:15px">По инструментам</h3>'
 +tbl(['Инструмент','Сделок','TP / SL / БУ','WR','ΣR','R / сделка','Макс. просадка'],[
   '<tr><td>%s</td><td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td>%s<td>%+.2fR</td><td>%s</td></tr>'%(k,s['n'],s['tp'],s['sl'],s['be'],s['wr'],cell(s['R']),s['avg'],dd(s['dd'])) for k,s in C['syms'].items()])
 +'<details style="margin-top:12px"><summary style="cursor:pointer;font-weight:600">▶ По месяцам (Тип C, правила с 08.10)</summary>'
 +tbl(['Месяц','Сделок','TP / SL / БУ','WR','ΣR','R / сделка','Макс. просадка','Макс. серия SL'],[
   '<tr><td>%s</td><td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td>%s<td>%+.2fR</td><td>%s</td><td>%d</td></tr>'%(mname(m),s['n'],s['tp'],s['sl'],s['be'],s['wr'],cell(s['R']),s['avg'],dd(s['dd']),s['st']) for m,s in C['months'].items()])
 +'</details></div>')
# 3. Combined card
a5,c5,t5=A['all'],C['all'],AC['all']
Comb=('<div class="card"><h2>Тип A + Тип C вместе · 5 лет и по годам</h2><p class="note">Оба типа по правилам Пульта на 08.10.2026 (Тип A — триггер ≤1,5 ATR → 2 сильные свечи, цель 2R; Тип C — откат 20%%, цель 3R, БУ 50%%), 7 инструментов для A и 3 для C, сделки сложены по датам. Просадка — от пика общей кривой ΣR внутри периода. Тип A здесь пересчитан тем же скриптом поштучно: за 5 лет это %s вместо +696.1R в таблицах Типа A выше (разница ~2%% из-за обработки закрытий в 22:00).</p>'%Rs(a5['R'])
 +'<div class="kpis">'+kpi('Сделок · 5 лет',t5['n'])+kpi('WR','%.1f%%'%t5['wr'])+kpi('ΣR · 5 лет',Rs(t5['R']),'pos')+kpi('R / сделка','%+.2fR'%t5['avg'])+kpi('Макс. просадка',dd(t5['dd']),'neg')+kpi('Макс. серия SL',t5['st'])+'</div>'
 +tbl(['Год','Тип A: сделок','Тип A: ΣR','Тип C: сделок','Тип C: ΣR','Вместе: сделок','TP / SL / БУ','WR','ΣR','R / сделка','Просадка','Серия SL'],
  ['<tr%s><td>%s</td><td>%d</td>%s<td>%d</td>%s<td>%d</td><td>%d / %d / %d</td><td>%.1f%%</td>%s<td>%+.2fR</td><td>%s</td><td>%d</td></tr>'%(
     ' class="tot"' if y=='all' else '',YN.get(int(y),y) if y!='all' else '5 лет · всего',
     (A['years'][y] if y!='all' else A['all'])['n'],cell((A['years'][y] if y!='all' else A['all'])['R']),
     (C['years'][y] if y!='all' else C['all'])['n'],cell((C['years'][y] if y!='all' else C['all'])['R']),
     s['n'],s['tp'],s['sl'],s['be'],s['wr'],cell(s['R']),s['avg'],dd(s['dd']),s['st'])
   for y,s in list(AC['years'].items())+[('all',AC['all'])]])
 +'<details style="margin-top:12px"><summary style="cursor:pointer;font-weight:600">▶ По месяцам (Тип A, Тип C и вместе)</summary>'
 +tbl(['Месяц','Тип A: сделок','Тип A: ΣR','Тип C: сделок','Тип C: ΣR','Вместе: сделок','WR','ΣR','Просадка в месяце'],
  ['<tr><td>%s</td><td>%d</td>%s<td>%d</td>%s<td>%d</td><td>%.1f%%</td>%s<td>%s</td></tr>'%(mname(m),A['months'].get(m,{'n':0})['n'],cell(A['months'].get(m,{'R':0})['R']),C['months'].get(m,{'n':0})['n'],cell(C['months'].get(m,{'R':0})['R']),s['n'],s['wr'],cell(s['R']),dd(s['dd'])) for m,s in AC['months'].items()])
 +'</details></div>')
open('c_card.html','w').write(Ccard);open('comb_card.html','w').write(Comb)
print(len(Ccard),len(Comb))
