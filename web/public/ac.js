/* Аналитика сделок A и C для Пульта (11.10.2026): графики M5/H1 с разметкой, сводка, карточки, комментарии.
   Данные — записи state/analytics.json (analytics_gen.py). Публичный API: window.AC. */
(function(){
'use strict';
var W=1000,Hh=470,L=66,R=150,T=54,Bt=34,HW=1000,HH=360;
var DECM={XAUUSD:2,EURUSD:5,GBPUSD:5,US500:1,NAS100:1,US30:0,GER40:1};
function dec(s){return DECM[s]!=null?DECM[s]:5}
function px(v,s){return Number(v).toFixed(dec(s))}
var CFG={A:{rr:2,b0:'03:00',b1:'09:55',s0:'10:00',bn:'Азия'},C:{rr:3,b0:'11:00',b1:'16:25',s0:'16:30',bn:'бокс'}};
function RT(c){return c.res==='TP'?'TP +'+c.rr+'R':c.res==='SL'?'SL −1R':c.res==='BE'?'БУ 0R':'22:00 '+(c.R>=0?'+':'−')+Math.abs(c.R).toFixed(2)+'R'}
function rcls(c){return c.res==='TP'?'w':c.res==='SL'?'l':c.res==='BE'?'b':'no'}
function fd(d){return d.split('-').reverse().join('.')}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]})}
function prep(c,k){var d=CFG[c.typ]||CFG.A;for(var key in d){if(c[key]==null)c[key]=d[key]}
  c.ext=c.ext==null?c.stop:Number(c.ext);c.R=Math.round(Number(c.R||0)*100)/100;if(c.typ==='A')c.be=null;if(k!=null)c.k=k;
  c.bars=c.bars||[];c.h1=c.h1||[];c.fvg=c.fvg||[];c.liq=c.liq||[];return c}
var uid=0;
function pills(arr,y0,y1){ // раздвигаем подписи по вертикали
  arr.sort((a,b)=>a.y-b.y);const gap=19;
  for(let i=0;i<arr.length;i++){if(i&&arr[i].y<arr[i-1].y+gap)arr[i].y=arr[i-1].y+gap}
  const over=arr.length?arr[arr.length-1].y-y1:0;if(over>0)arr.forEach(p=>p.y-=over);
  for(let i=0;i<arr.length;i++){if(arr[i].y<y0)arr[i].y=y0}
  for(let i=1;i<arr.length;i++){if(arr[i].y<arr[i-1].y+gap)arr[i].y=arr[i-1].y+gap}
  return arr}
function pill(p,x,w){const bw=w;return `<line x1="${x-6}" x2="${x}" y1="${p.y0}" y2="${p.y}" stroke="${p.c}" stroke-width="1"/><rect x="${x}" y="${p.y-9}" width="${bw}" height="18" rx="9" fill="${p.c}"/><text x="${x+bw/2}" y="${p.y+4}" text-anchor="middle" style="fill:#fff;font-weight:600;font-size:11px">${p.t}</text>`}
const tsB=(c)=>c.day+' ';
function m5chart(c,zoom,ci){
  const B=c.bars,sd=c.side==='long'?1:-1,s=c.sym;
  const idx=t=>B.findIndex(b=>b[4]===t);
  let iE=idx(c.tin);if(iE<0)iE=Math.max(0,B.findIndex(b=>b[4]>=c.tin));let iX=idx(c.xt);if(iX<0)iX=B.length-1;
  const ge=t=>{const j=B.findIndex(b=>b[4]>=t);return j<0?B.length-1:j};const iB0=ge(c.b0),iB1=Math.max(iB0,ge(c.b1)),iS0=ge(c.s0);
  let iG=iS0;for(let i=iS0;i<=iE;i++){if(sd==1?B[i][2]<=B[iG][2]:B[i][1]>=B[iG][1])iG=i}
  let iF=iS0;for(let i=iS0;i<=iG;i++){if(sd==1?B[i][2]<c.boxL:B[i][1]>c.boxH){iF=i;break}}
  let a=0,z=B.length-1;if(zoom==='trade'){a=Math.max(0,iB1-12);z=Math.min(B.length-1,Math.max(iX,iE)+16)}
  const n=z-a+1,cw=(W-L-R)/n,x=i=>L+cw*(i-a+0.5);
  let lo=Infinity,hi=-Infinity;for(let i=a;i<=z;i++){lo=Math.min(lo,B[i][2]);hi=Math.max(hi,B[i][1])}
  lo=Math.min(lo,c.stop,c.tp,c.boxL);hi=Math.max(hi,c.stop,c.tp,c.boxH);
  const pad=(hi-lo)*.05;lo-=pad;hi+=pad;const y=v=>T+(Hh-T-Bt)*(1-(v-lo)/(hi-lo));
  const cid='cc'+ci,PL=Hh-Bt;
  let s_=`<svg viewBox="0 0 ${W} ${Hh}" role="img" aria-label="График M5 ${c.sym} ${c.day}"><defs><clipPath id="${cid}"><rect x="${L}" y="${T}" width="${W-L-R}" height="${PL-T}"/></clipPath></defs>`;
  for(let q=0;q<=5;q++){const v=lo+(hi-lo)*q/5,yy=y(v);s_+=`<line x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}" stroke="var(--a-grid)"/><text x="${L-6}" y="${yy+4}" text-anchor="end">${px(v,s)}</text>`}
  const hs=zoom==='trade'?1:2;
  for(let i=a;i<=z;i++){const t=B[i][4];if(t.slice(3)==='00'&&(hs===1||(+t.slice(0,2))%2===0)){const xx=x(i);s_+=`<line x1="${xx}" x2="${xx}" y1="${T}" y2="${PL}" stroke="var(--a-grid)"/><text x="${xx}" y="${PL+16}" text-anchor="middle">${t}</text>`}}
  s_+=`<g clip-path="url(#${cid})">`;
  // H1 FVG: только неинвертированные; обрыв, когда H1 закрылась за дальней границей
  const hr=t=>{const [h,m]=t.split(':');return +h*60+ +m};
  const hourClose=[];for(let i=0;i<B.length;i++){if(B[i][4].slice(3)==='55')hourClose.push([i,B[i][3]])}
  c.fvg.forEach(f=>{const col=f[3]===1?'var(--a-fvgu)':'var(--a-fvgd)';
    let x0=L;const sday=f[0].slice(0,10);if(sday===c.day){const j=idx(f[0].slice(11));if(j>=0)x0=Math.max(L,x(j)-cw/2)}else if(sday>c.day)return;
    let x1=W-R;
    for(const [i,cl] of hourClose){if(i<=iE)continue;if(f[3]===1?cl<f[1]:cl>f[2]){x1=Math.min(x1,x(i)+cw/2);break}}
    if(f[2]<lo||f[1]>hi)return;
    s_+=`<rect x="${x0}" y="${y(f[2])}" width="${Math.max(0,x1-x0)}" height="${Math.max(2,y(f[1])-y(f[2]))}" fill="${col}" opacity=".16"/><line x1="${x0}" x2="${x1}" y1="${y(f[2])}" y2="${y(f[2])}" stroke="${col}" stroke-width=".7" opacity=".5"/><line x1="${x0}" x2="${x1}" y1="${y(f[1])}" y2="${y(f[1])}" stroke="${col}" stroke-width=".7" opacity=".5"/>`});
  // бокс и вынос
  const xa=x(Math.max(a,iB0))-cw/2,xb=x(iB1)+cw/2;
  s_+=`<rect x="${xa}" y="${y(c.boxH)}" width="${Math.max(0,xb-xa)}" height="${y(c.boxL)-y(c.boxH)}" fill="var(--a-asia-bg)" stroke="var(--a-asia)"/>`;
  [c.boxH,c.boxL].forEach(v=>{s_+=`<line x1="${Math.max(L,xb)}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--a-asia)" stroke-dasharray="4 4" opacity=".8"/>`});
  s_+=`<rect x="${x(iF)-cw/2}" y="${T}" width="${x(iG)-x(iF)+cw}" height="${PL-T}" fill="var(--a-sweep-bg)"/>`;
  // ликвидность: тонкая зелёная линия от точки, обрыв на снятии
  c.liq.forEach(q=>{const p=q[0];if(p<lo||p>hi)return;let x0=L,dot=null;const sday=q[2].slice(0,10);
    if(sday===c.day){const j=B.findIndex(b=>b[4]>=q[2].slice(11));if(j>=0){x0=Math.max(L,x(j));dot=x(j)}}else if(sday>c.day)return;
    let x1=W-R;const jf=Math.max(0,idx('00:00'));
    for(let i=0;i<B.length;i++){if(i<iE)continue;if(q[1]==='hi'?B[i][1]>p:B[i][2]<p){x1=Math.min(x1,x(i));break}}
    if(x1<=x0)return;
    s_+=`<line x1="${x0}" x2="${x1}" y1="${y(p)}" y2="${y(p)}" stroke="var(--a-liqln)" stroke-width="1"/>`;
    if(dot!==null&&dot>=L)s_+=`<circle cx="${dot}" cy="${y(p)}" r="3.4" fill="var(--a-panel)" stroke="var(--a-liqln)" stroke-width="1.4"/>`});
  const xe=x(iE)-cw/2,xx=x(iX)+cw/2;
  s_+=`<rect x="${xe}" y="${Math.min(y(c.entry),y(c.tp))}" width="${xx-xe}" height="${Math.abs(y(c.entry)-y(c.tp))}" fill="var(--a-tp)" opacity=".22"/><rect x="${xe}" y="${Math.min(y(c.entry),y(c.stop))}" width="${xx-xe}" height="${Math.abs(y(c.entry)-y(c.stop))}" fill="var(--a-sl)" opacity=".22"/>`;
  [[c.tp,'var(--a-tp)',2,'6 3'],[c.stop,'var(--a-sl)',2,'6 3'],[c.entry,'var(--a-entry)',2,''],[c.be,'var(--a-be)',1.8,'3 3']].filter(q=>q[0]!=null).forEach(q=>{s_+=`<line x1="${xe}" x2="${W-R}" y1="${y(q[0])}" y2="${y(q[0])}" stroke="${q[1]}" stroke-width="${q[2]}" ${q[3]?`stroke-dasharray="${q[3]}"`:''} opacity="1"/>`});
  for(let i=a;i<=z;i++){const b=B[i],up=b[3]>=b[0],col=up?'var(--a-up)':'var(--a-dn)',xc=x(i);
    s_+=`<line x1="${xc}" x2="${xc}" y1="${y(b[1])}" y2="${y(b[2])}" stroke="${col}"/><rect x="${xc-cw*.34}" y="${Math.min(y(b[0]),y(b[3]))}" width="${cw*.68}" height="${Math.max(1,Math.abs(y(b[0])-y(b[3])))}" fill="${col}"/>`}
  const ey=y(c.ext);s_+=`<circle cx="${x(iG)}" cy="${ey}" r="4.5" fill="none" stroke="var(--a-mark)" stroke-width="1.6"/>`;
  {const t='экстремум '+px(c.ext,s),w=t.length*6.4+14,ly=Math.max(T+12,ey-22),lx=Math.max(L+w,x(iG)-10);
   s_+=`<line x1="${lx-4}" y1="${ly+9}" x2="${x(iG)-3}" y2="${ey-3}" stroke="var(--a-mark)" stroke-width="1"/><rect x="${lx-w}" y="${ly-9}" width="${w}" height="18" rx="9" fill="var(--a-mark)"/><text x="${lx-w/2}" y="${ly+4}" text-anchor="middle" style="fill:#fff;font-weight:600;font-size:11px">${t}</text>`}
  {const bx=Math.max(L,xa)+6;
   s_+=`<text class="halo" x="${bx}" y="${y(c.boxH)+14}" style="fill:var(--a-asia);font-weight:700;font-size:11px">${c.bn} хай ${px(c.boxH,s)}</text><text class="halo" x="${bx}" y="${y(c.boxL)-7}" style="fill:var(--a-asia);font-weight:700;font-size:11px">${c.bn} лой ${px(c.boxL,s)}</text>`}
  s_+='</g>';
  // вход / выход: кружки на графике, подписи в верхней полосе
  const ye=c.res==='TP'?c.tp:c.res==='SL'?c.stop:c.res==='BE'?c.entry:B[iX][3];
  const col=c.res==='TP'?'var(--a-tp)':c.res==='SL'?'var(--a-sl)':c.res==='BE'?'var(--a-be)':'var(--a-muted)';
  s_+=`<line x1="${x(iE)}" x2="${x(iE)}" y1="${T}" y2="${PL}" stroke="var(--a-entry)" stroke-width="1.2" stroke-dasharray="2 3"/><circle cx="${x(iE)}" cy="${y(c.entry)}" r="6" fill="var(--a-entry)" stroke="var(--a-panel)" stroke-width="2"/><circle cx="${x(iX)}" cy="${y(ye)}" r="5.5" fill="${col}" stroke="var(--a-panel)" stroke-width="2"/>`;
  const l1=`ВХОД ${c.tin} · ${px(c.entry,s)}`,w1=l1.length*7+16,x1c=Math.min(W-R-w1,Math.max(L,x(iE)-w1/2));
  const l2=`${RT(c)} · ${c.xt}`,w2=l2.length*7+16,x2c=Math.min(W-R-w2,Math.max(L,x(iX)-w2/2));
  s_+=`<rect x="${x1c}" y="6" width="${w1}" height="20" rx="10" fill="var(--a-entry)"/><text x="${x1c+w1/2}" y="20" text-anchor="middle" style="fill:#fff;font-weight:700;font-size:12px">${l1}</text>`;
  s_+=`<line x1="${x(iX)}" x2="${x(iX)}" y1="30" y2="${T}" stroke="${col}" stroke-width="1"/><rect x="${x2c}" y="30" width="${w2}" height="20" rx="10" fill="${col}"/><text x="${x2c+w2/2}" y="44" text-anchor="middle" style="fill:#fff;font-weight:700;font-size:12px">${l2}</text>`;
  // правое поле: подписи уровней
  const P=[{v:c.tp,c:'var(--a-tp)',t:'цель '+c.rr+'R '+px(c.tp,s)},...(c.be!=null?[{v:c.be,c:'var(--a-be)',t:'БУ-порог '+px(c.be,s)}]:[]),{v:c.entry,c:'var(--a-entry)',t:'вход '+px(c.entry,s)},{v:c.stop,c:'var(--a-sl)',t:'стоп '+px(c.stop,s)}].map(p=>({y0:y(p.v),y:y(p.v),c:p.c,t:p.t}));
  pills(P,T+9,PL-9).forEach(p=>{s_+=pill(p,W-R+10,R-14)});
  s_+=`<line id="xc${ci}" y1="${T}" y2="${PL}" stroke="var(--a-fg)" opacity="0"/><rect id="oc${ci}" x="${L}" y="${T}" width="${W-L-R}" height="${PL-T}" fill="transparent" style="cursor:crosshair"/></svg>`;
  return {svg:s_,a,z,cw,x};
}
function h1chart(c){
  const B=c.h1,sd=c.side==='long'?1:-1,s=c.sym,n=B.length,ex=18,N=n+ex,Rm=150,cw=(HW-L-Rm)/N,x=i=>L+cw*(i+.5);
  let lo=Infinity,hi=-Infinity;B.forEach(b=>{lo=Math.min(lo,b[2]);hi=Math.max(hi,b[1])});
  lo=Math.min(lo,c.stop);hi=Math.max(hi,c.tp);const pad=(hi-lo)*.05;lo-=pad;hi+=pad;const T2=14,B2=HH-30,y=v=>T2+(B2-T2)*(1-(v-lo)/(hi-lo));
  const find=t=>{let j=B.findIndex(b=>b[4]>=t);return j};
  let o=`<svg viewBox="0 0 ${HW} ${HH}" role="img" aria-label="График H1 ${c.sym} за 7 суток">`;
  for(let q=0;q<=5;q++){const v=lo+(hi-lo)*q/5,yy=y(v);o+=`<line x1="${L}" x2="${HW-Rm}" y1="${yy}" y2="${yy}" stroke="var(--a-grid)"/><text x="${L-6}" y="${yy+4}" text-anchor="end">${px(v,s)}</text>`}
  let last='',lx=-99;B.forEach((b,i)=>{const d=b[4].slice(5,10).split('-').reverse().join('.');if(d!==last){last=d;const xx=x(i)-cw/2;o+=`<line x1="${xx}" x2="${xx}" y1="${T2}" y2="${B2}" stroke="var(--a-line)"/>`;if(xx-lx>38){o+=`<text x="${xx+3}" y="${B2+16}">${d}</text>`;lx=xx}}});
  const dayI=B.findIndex(b=>b[4].slice(0,10)===c.day);
  if(dayI>=0)o+=`<rect x="${x(dayI)-cw/2}" y="${T2}" width="${x(n-1)-x(dayI)+cw}" height="${B2-T2}" fill="var(--a-sweep-bg)" opacity=".5"/>`;
  c.fvg.forEach(f=>{let j=find(f[0]);if(j<0)j=0;const col=f[3]===1?'var(--a-fvgu)':'var(--a-fvgd)',x0=x(j)-cw/2;
    if(f[2]<lo||f[1]>hi)return;
    o+=`<rect x="${x0}" y="${y(f[2])}" width="${HW-Rm-x0}" height="${Math.max(2,y(f[1])-y(f[2]))}" fill="${col}" opacity=".18"/><line x1="${x0}" x2="${HW-Rm}" y1="${y(f[2])}" y2="${y(f[2])}" stroke="${col}" stroke-width=".7" opacity=".55"/><line x1="${x0}" x2="${HW-Rm}" y1="${y(f[1])}" y2="${y(f[1])}" stroke="${col}" stroke-width=".7" opacity=".55"/>`});
  c.liq.forEach(q=>{const p=q[0];if(p<lo||p>hi)return;let j=find(q[2]);const dot=j>=0;if(j<0)j=0;
    o+=`<line x1="${x(j)}" x2="${HW-Rm}" y1="${y(p)}" y2="${y(p)}" stroke="var(--a-liqln)" stroke-width="1"/>`+(dot?`<circle cx="${x(j)}" cy="${y(p)}" r="3.4" fill="var(--a-panel)" stroke="var(--a-liqln)" stroke-width="1.4"/>`:'')});
  const xe=x(n-1)+cw/2;
  o+=`<rect x="${xe}" y="${Math.min(y(c.entry),y(c.tp))}" width="${HW-Rm-xe}" height="${Math.abs(y(c.entry)-y(c.tp))}" fill="var(--a-tp)" opacity=".24"/><rect x="${xe}" y="${Math.min(y(c.entry),y(c.stop))}" width="${HW-Rm-xe}" height="${Math.abs(y(c.entry)-y(c.stop))}" fill="var(--a-sl)" opacity=".24"/>`;
  [[c.tp,'var(--a-tp)','6 3'],[c.stop,'var(--a-sl)','6 3'],[c.entry,'var(--a-entry)','']].forEach(q=>{o+=`<line x1="${xe}" x2="${HW-Rm}" y1="${y(q[0])}" y2="${y(q[0])}" stroke="${q[1]}" stroke-width="2" ${q[2]?`stroke-dasharray="${q[2]}"`:''}/>`});
  B.forEach((b,i)=>{const up=b[3]>=b[0],col=up?'var(--a-up)':'var(--a-dn)',xc=x(i);o+=`<line x1="${xc}" x2="${xc}" y1="${y(b[1])}" y2="${y(b[2])}" stroke="${col}"/><rect x="${xc-cw*.34}" y="${Math.min(y(b[0]),y(b[3]))}" width="${cw*.68}" height="${Math.max(1,Math.abs(y(b[0])-y(b[3])))}" fill="${col}"/>`});
  const P=[{v:c.tp,c:'var(--a-tp)',t:'цель '+px(c.tp,s)},{v:c.entry,c:'var(--a-entry)',t:'вход '+px(c.entry,s)},{v:c.stop,c:'var(--a-sl)',t:'стоп '+px(c.stop,s)}].map(p=>({y0:y(p.v),y:y(p.v),c:p.c,t:p.t}));
  pills(P,T2+9,B2-9).forEach(p=>{o+=pill(p,HW-Rm+10,Rm-14)});
  return `<div class="scr">${o}</svg></div>`}
// ---------- карточка сделки ----------
function drawM5(el,c,st){
  var ci=st.ci,m=m5chart(c,st.z,ci);
  el.querySelector('.ctl').innerHTML='<button type="button" class="zb'+(st.z==='trade'?' on':'')+'" data-z="trade">Крупно</button><button type="button" class="zb'+(st.z==='day'?' on':'')+'" data-z="day">Весь день</button>';
  el.querySelector('.chart').innerHTML='<div class="scr">'+m.svg+'</div><div class="tip" hidden></div>';
  var svg=el.querySelector('svg'),ov=svg.querySelector('#oc'+ci),xh=svg.querySelector('#xc'+ci),tip=el.querySelector('.tip');
  function mv(e){var r=svg.getBoundingClientRect(),vx=(e.clientX-r.left)/r.width*W,i=Math.min(m.z,Math.max(m.a,m.a+Math.floor((vx-L)/m.cw))),b=c.bars[i];if(!b)return;
    xh.setAttribute('x1',m.x(i));xh.setAttribute('x2',m.x(i));xh.setAttribute('opacity','.5');
    tip.hidden=false;tip.innerHTML='<b>'+b[4]+'</b> O '+px(b[0],c.sym)+' H '+px(b[1],c.sym)+' L '+px(b[2],c.sym)+' C '+px(b[3],c.sym)+(b[4]===c.tin?'<br><span class="tg">вход</span>':'')+(b[4]===c.xt?'<br><span class="tg">выход</span>':'');
    var cr=el.querySelector('.chart').getBoundingClientRect();var tx=e.clientX-cr.left+14;if(tx>cr.width-300)tx=e.clientX-cr.left-310;tip.style.left=Math.max(4,tx)+'px';tip.style.top=Math.max(4,e.clientY-cr.top-50)+'px'}
  ov.addEventListener('pointermove',mv);ov.addEventListener('pointerdown',mv);ov.addEventListener('pointerleave',function(){tip.hidden=true;xh.setAttribute('opacity','0')});
  el.querySelectorAll('[data-z]').forEach(function(b){b.onclick=function(){st.z=b.dataset.z;drawM5(el,c,st)}});
}

// api комментариев: {load:()=>Promise<{id:{text,at}}>, save:(id,text)=>Promise}; без api блок комментария не рисуется
function cardEl(c,opts){
  opts=opts||{};var sd=c.side==='long'?1:-1,risk=Math.abs(c.entry-c.stop),ci='u'+(++uid);
  var el=document.createElement('article');el.className='card';el.id=opts.id||('card'+ci);
  var hasH1=c.h1&&c.h1.length>=5;
  el.innerHTML='<div class="hd"><span class="t">'+(opts.title||(c.typ+(c.k||'')+'. '+c.sym))+'</span><span class="muted">'+fd(c.day)+'</span><span class="pill '+(sd==1?'long':'short')+'">'+(sd==1?'LONG':'SHORT')+'</span><span class="res '+(c.res==='TP'?'win':c.res==='SL'?'loss':c.res==='BE'?'be':'')+'">'+RT(c)+'</span>'+(c.rk!=null?'<span class="res" style="font-weight:700">стоп '+Number(c.rk).toFixed(2).replace('.',',')+' ATR</span>':'')+'</div>'
   +'<div class="info"><span class="e">вход '+c.tin+' по '+px(c.entry,c.sym)+'</span> · <span class="s">стоп '+px(c.stop,c.sym)+'</span> (риск '+px(risk,c.sym)+')'+(c.be!=null?' · БУ-порог '+px(c.be,c.sym):'')+' · <span class="t">цель '+c.rr+'R '+px(c.tp,c.sym)+'</span> · выход '+c.xt+'</div>'
   +'<div class="ctl"></div><div class="chart"></div>'
   +(hasH1?'<div class="sub">H1 за 7 суток до входа: зоны FVG и неснятая ликвидность</div>'+h1chart(c):'')
   +(opts.api?'<div class="cm"><label for="cm'+ci+'">Комментарий к сделке '+c.typ+(c.k||'')+'</label><textarea id="cm'+ci+'" placeholder="Что видно: вход, стоп, цель, что бы вы изменили"></textarea><div class="cms" id="cs'+ci+'"></div></div>':'');
  if(c.bars.length>5)drawM5(el,c,{z:opts.zoom||'trade',ci:ci});else{el.querySelector('.chart').innerHTML='<div class="empty">Нет свечей M5 для графика</div>'}
  if(opts.api){var ta=el.querySelector('#cm'+ci),stt=el.querySelector('#cs'+ci),cid=c.typ+'_'+c.sym+'_'+c.day,t=null,dirty=false;
    opts.api.load().then(function(map){var v=map&&map[cid];if(v&&typeof v.text==='string'&&!dirty)ta.value=v.text}).catch(function(){stt.textContent='Комментарии пока не загрузились'});
    ta.addEventListener('input',function(){dirty=true;stt.textContent='Сохраняю…';clearTimeout(t);t=setTimeout(function(){opts.api.save(cid,ta.value,{sym:c.sym,day:c.day,n:c.k,typ:c.typ}).then(function(){dirty=false;stt.textContent='Сохранено'}).catch(function(){stt.textContent='Не удалось сохранить'})},700)});}
  return el;
}

// ---------- сводка ----------
function summ(list,typ,statsEl,tblEl,cards){
  var D=list;if(!D.length){statsEl.innerHTML='';tblEl.innerHTML='';return {typ:typ,n:0,tp:0,sl:0,be:0,t22:0,cum:0,dd:0,ms:0}}
  var cum=0,pk=0,dd=0,st=0,ms=0;D.forEach(function(c){cum+=c.R;pk=Math.max(pk,cum);dd=Math.min(dd,cum-pk);if(c.res==='SL'){st++;ms=Math.max(ms,st)}else if(c.R>0.05)st=0});
  var n=D.length,tp=D.filter(function(c){return c.res==='TP'}).length,be=D.filter(function(c){return c.res==='BE'}).length,sl=D.filter(function(c){return c.res==='SL'}).length,t22=n-tp-be-sl;
  var sg=function(v){return (v>=0?'+':'−')+Math.abs(v).toFixed(2)};
  var q=[['Сделок',n,''],['TP',tp,'w'],typ==='C'?['БУ',be,'b']:['22:00',t22,'no'],['SL',sl,'l'],['Доля TP',Math.round(100*tp/n)+'%',''],['Итог',sg(cum)+'R',cum>=0?'w':'l'],['При риске 1%',sg(cum)+'%',cum>=0?'w':'l'],['Просадка',(dd===0?'0':'−'+Math.abs(dd).toFixed(2))+'R',''],['Серия SL',ms,'']];
  statsEl.innerHTML=q.map(function(x){return '<div class="c2st"><b class="'+x[2]+'">'+x[1]+'</b><span>'+x[0]+'</span></div>'}).join('');
  tblEl.innerHTML='<thead><tr><th>#</th><th>Пара</th><th>Дата</th><th>Сторона</th><th>Вход</th><th>Выход</th><th>Итог</th><th>Оценка</th></tr></thead><tbody>'+D.map(function(c,i){return '<tr class="go" data-i="'+i+'"><td class="n">'+typ+c.k+'</td><td>'+c.sym+'</td><td class="n">'+fd(c.day)+'</td><td>'+(c.side==='long'?'LONG':'SHORT')+'</td><td class="n">'+c.tin+' · '+px(c.entry,c.sym)+'</td><td class="n">'+c.xt+'</td><td class="'+rcls(c)+'">'+RT(c)+'</td><td>'+esc(c.prob||'—')+'</td></tr>'}).join('')+'</tbody>';
  tblEl.querySelectorAll('tr.go').forEach(function(r){r.onclick=function(){var el=cards[+r.dataset.i];if(el)el.scrollIntoView({behavior:'smooth',block:'start'})}});
  return {typ:typ,n:n,tp:tp,sl:sl,be:be,t22:t22,cum:cum,dd:dd,ms:ms,from:D[0].day,to:D[D.length-1].day};
}

var RULES_A='<div class="rules"><span><b>Правила Типа A.</b> Бокс Азии 03:00–10:00, сторона определяется по сравнению с вчерашней Азией (хай выше — только лонг, лой ниже — только шорт). Вынос противоположной границы бокса в окне 10:00–14:00, вынос не меньше 0,5 ATR, V-разворот не больше 7 значимых свечей, вход по открытию следующей свечи.</span><span>Стоп за экстремумом выноса минус 0,3 ATR, цель 2R, скип при встречном H1 FVG внутри цели, остаток закрывается в 22:00. Безубытка у Типа A нет.</span></div>';
var RULES_C='<div class="rules"><span><b>Правила Типа C.</b> Бокс Лондона 11:00–16:25, вынос после 16:30, вход на откате 20% длины выноса, окно входа до 18:30. Стоп за экстремумом: экстремум минус 0,1 от расстояния до входа. Цель 3R, на 50% пути стоп уходит в БУ, остаток закрывается в 22:00.</span><span>Скипы: больше 4 недожи-свечей выноса, широкий M5 FVG от 2 средних свечей, риск меньше 0,25 ATR, встречный H1 FVG внутри цели 1:3. Инструменты: XAUUSD, EURUSD, GBPUSD.</span></div>';
function legend(bn,rr,be){return '<div class="legend"><span><i style="background:var(--a-asia-bg);border:1px solid var(--a-asia)"></i>бокс '+bn+'</span><span><i style="background:var(--a-sweep-bg)"></i>вынос</span><span><i style="background:var(--a-fvgu);opacity:.4"></i>H1 FVG вверх</span><span><i style="background:var(--a-fvgd);opacity:.4"></i>H1 FVG вниз</span><span><i class="ln"></i>неснятая ликвидность</span><span><i style="background:var(--a-entry)"></i>вход</span><span><i style="background:var(--a-sl)"></i>стоп</span><span><i style="background:var(--a-tp)"></i>цель '+rr+'R</span>'+(be?'<span><i style="background:var(--a-be)"></i>БУ-порог 50%</span>':'')+'</div>'}

// ---------- вкладка целиком: data = {A:[...], C:[...]} ----------
function mountTab(root,data,api){
  root.classList.add('acx');
  var A=(data.A||[]).slice(),C=(data.C||[]).slice();
  var cmp=function(a,b){return a.day<b.day?-1:a.day>b.day?1:a.tin<b.tin?-1:a.tin>b.tin?1:a.sym<b.sym?-1:1};
  A.sort(cmp);C.sort(cmp);A.forEach(function(c,i){prep(c,i+1)});C.forEach(function(c,i){prep(c,i+1)});
  root.innerHTML='<div class="wrap"><header style="display:flex;flex-direction:column;gap:12px"><h2 style="font-size:1.5rem">Аналитика сделок</h2><p class="lead">Последние 10 сделок Типа A и Типа C: новая сделка добавляется после закрытия, самая старая уходит. Время везде UTC+3. Нажмите строку таблицы, чтобы перейти к графику сделки; под графиком можно оставить комментарий, разбор по нему я даю в чате.</p><div class="seg" role="tablist"><button type="button" class="on tbA" role="tab">Тип A <small>Азия → выход, цель 2R</small></button><button type="button" class="tbC" role="tab">Тип C <small>Лондон → Нью-Йорк, цель 3R</small></button></div></header>'
   +'<div class="tbl"><table class="top"></table></div>'
   +'<section class="pane paneA">'+RULES_A+'<h2>Тип A: последние '+A.length+' сделок</h2><div class="c2stats statsA"></div>'+legend('Азии',2,false)+'<div class="tbl"><table class="sumA"></table></div><div class="cards cardsA"></div></section>'
   +'<section class="pane paneC" hidden>'+RULES_C+'<h2>Тип C: последние '+C.length+' сделок</h2><div class="c2stats statsC"></div>'+legend('Лондона',3,true)+'<div class="tbl"><table class="sumC"></table></div><div class="cards cardsC"></div></section>'
   +'<p class="muted" style="font-size:.84rem">Показаны только неинвертированные H1 FVG и неснятая ликвидность на момент входа. Подписи уровней стоят в правом поле. Наведите курсор на свечу, чтобы увидеть цены. Расчёт движком Пульта, не торговая рекомендация.</p></div>';
  var q=function(s){return root.querySelector(s)};
  [['A',A],['C',C]].forEach(function(p){var typ=p[0],list=p[1],host=q('.cards'+typ);
    if(!list.length)host.innerHTML='<div class="empty">Пока нет закрытых сделок Типа '+typ+'. Они появятся здесь после закрытия первой сделки.</div>';
    var els=list.map(function(c){var el=cardEl(c,{api:api});host.appendChild(el);return el});
    p.push(summ(list,typ,q('.stats'+typ),q('.sum'+typ),els));
  });
  var SA=[].concat([]),sg=function(v){return (v>=0?'+':'−')+Math.abs(v).toFixed(2)+'R'};
  var rows=[ ['A',A,2],['C',C,3] ].map(function(p){var list=p[1];if(!list.length)return '';var cum=0,pk=0,dd=0;list.forEach(function(c){cum+=c.R;pk=Math.max(pk,cum);dd=Math.min(dd,cum-pk)});
    var cnt=function(r){return list.filter(function(c){return c.res===r}).length},tp=cnt('TP'),be=cnt('BE'),sl=cnt('SL'),t22=list.length-tp-be-sl;
    return '<tr><td><b>Тип '+p[0]+'</b></td><td class="n">'+fd(list[0].day).slice(0,5)+'–'+fd(list[list.length-1].day).slice(0,5)+'</td><td class="n">'+list.length+'</td><td class="w n">'+tp+'</td><td class="b n">'+be+'</td><td class="no n">'+t22+'</td><td class="l n">'+sl+'</td><td class="n '+(cum>=0?'w':'l')+'">'+sg(cum)+'</td><td class="n">'+(dd===0?'0R':'−'+Math.abs(dd).toFixed(2)+'R')+'</td></tr>'}).join('');
  q('.top').innerHTML='<thead><tr><th>Тип</th><th>Период</th><th>Сделок</th><th>TP</th><th>БУ</th><th>22:00</th><th>SL</th><th>Итог</th><th>Просадка</th></tr></thead><tbody>'+rows+'</tbody>';
  var bA=q('.tbA'),bC=q('.tbC'),pA=q('.paneA'),pC=q('.paneC');
  function tab(c){pA.hidden=c;pC.hidden=!c;bA.classList.toggle('on',!c);bC.classList.toggle('on',c)}
  bA.onclick=function(){tab(false)};bC.onclick=function(){tab(true)};
}

// ---------- график сделки внутри чужой карточки (История, Чек-лист) ----------
function chartInto(host,c,opts){
  opts=opts||{};host.classList.add('acx','mini');host.innerHTML='';
  host.appendChild(cardEl(prep(c),{title:opts.title||(c.typ+' · '+c.sym),zoom:opts.zoom||'trade',api:null}));
}

window.AC={prep:prep,mountTab:mountTab,chartInto:chartInto,m5chart:m5chart,h1chart:h1chart,cardEl:cardEl,RT:RT,version:'11.10.2026'};
})();
