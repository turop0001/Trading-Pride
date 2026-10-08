//+------------------------------------------------------------------+
//| PultBridge.mq5 — исполнитель сигналов «Пульта входа» (ДЕМО)       |
//| Сам ничего не анализирует: раз в PollSec секунд читает сигналы     |
//| с сайта Пульта и открывает сделку с риском RiskPercent % баланса.  |
//| Стоп и тейк переносятся как РАССТОЯНИЯ от цены входа сигнала.      |
//| По умолчанию TradeEnabled=false — только пишет решения в журнал.   |
//| v1.10: раз в минуту шлёт свечи M5/H1/D1 брокера на сайт (/api/feed) |
//| — Пульт считает сигналы по ценам Tickmill, а не Yahoo.            |
//| v1.20 (08.10.2026): Тип C — отложенный stop-ордер на уровне 20%     |
//|   сразу после ВЫНОСА (двигается вместе с экстремумом); перенос стопа |
//|   в БУ на 50% пути (Тип C); Тип A — если цена ушла, лимит на откат  |
//|   к цене сигнала; свечи шлются каждые 20 с в окнах, опрос каждые 10 с|
//+------------------------------------------------------------------+
#property copyright "Trading Pride"
#property version   "1.20"
#include <Trade/Trade.mqh>

input string SignalsURL      = "https://trading-pride-three.vercel.app/api/signals";
input string FeedURL         = "https://trading-pride-three.vercel.app/api/feed";
input string FeedKey         = "";      // ключ личного пульта (последняя часть адреса /p/...)
input bool   FeedEnabled     = true;    // слать свечи брокера в Пульт
input int    FeedSec         = 60;
input int    FastFeedSec     = 20;      // в окнах A/C (UTC 06:30–11:30 и 13:00–16:00) свечи шлём чаще
input bool   PendEnabled     = true;    // Тип C: stop-ордер на уровне 20% после выноса (нужен TradeEnabled=true)
input bool   LimitOnMissA    = true;    // Тип A: цена ушла от входа — лимит на откат к цене сигнала
input bool   MoveToBE        = true;    // Тип C: стоп в безубыток на 50% пути к цели
input bool   TradeEnabled    = false;   // false = только журнал, без сделок
input bool   DemoOnly        = true;    // не торговать на реальном счёте
input double RiskPercent     = 1.0;     // риск на сделку, % баланса
input int    PollSec         = 10;
input int    MaxSignalAgeMin = 10;      // сигнал старше — пропуск
input double MaxDriftOfStop  = 0.30;    // цена ушла от входа больше доли стопа — пропуск
input int    MaxEntriesDay   = 3;
input int    StopAfterLosses = 2;
input bool   OneIdeaPerGroup = true;
input long   MagicNumber     = 770077;
input int    DeviationPts    = 30;
input string MapEURUSD = "EURUSD";
input string MapGBPUSD = "GBPUSD";
input string MapXAUUSD = "XAUUSD";
input string MapUS500  = "US500";
input string MapNAS100 = "USTEC";
input string MapUS30   = "US30";
input string MapGER40  = "DE40";

CTrade trade;
datetime lastFeed=0, lastFull=0, lastPoll=0;
string NAMES[7] = {"EURUSD","GBPUSD","XAUUSD","US500","NAS100","US30","GER40"};

string BrokerSym(const string s)
{
   if(s=="EURUSD") return MapEURUSD;  if(s=="GBPUSD") return MapGBPUSD;
   if(s=="XAUUSD") return MapXAUUSD;  if(s=="US500")  return MapUS500;
   if(s=="NAS100") return MapNAS100;  if(s=="US30")   return MapUS30;
   if(s=="GER40")  return MapGER40;   return "";
}
int GroupOf(const string s) { return (s=="US500"||s=="NAS100"||s=="US30"||s=="GER40") ? 1 : 2; }

int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(DeviationPts);
   bool demo = AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO;
   Print("PultBridge: счёт ", AccountInfoInteger(ACCOUNT_LOGIN), demo?" (ДЕМО)":" (РЕАЛЬНЫЙ)",
         TradeEnabled?", торговля ВКЛ":", только журнал");
   EventSetTimer(5);
   OnTimer();
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { EventKillTimer(); }

void Done(const string gv, const string msg) { if(msg!="") Print(msg); GlobalVariableSet(gv,0); }

void TodayStats(int &entries, int &losses)
{
   entries=0; losses=0;
   MqlDateTime d; TimeToStruct(TimeCurrent(), d); d.hour=0; d.min=0; d.sec=0;
   if(!HistorySelect(StructToTime(d), TimeCurrent()+60)) return;
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong tk=HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(tk,DEAL_MAGIC)!=MagicNumber) continue;
      long en=HistoryDealGetInteger(tk,DEAL_ENTRY);
      if(en==DEAL_ENTRY_IN) entries++;
      if(en==DEAL_ENTRY_OUT && HistoryDealGetDouble(tk,DEAL_PROFIT)<0) losses++;
   }
}

bool GroupBusy(const int grp, const bool isBuy)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(!PositionSelectByTicket(tk) || PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      string ps=PositionGetString(POSITION_SYMBOL);
      bool pb=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
      for(int k=0;k<7;k++) if(BrokerSym(NAMES[k])==ps && GroupOf(NAMES[k])==grp && pb==isBuy) return true;
   }
   return false;
}

bool InFastWindow()
{
   MqlDateTime g; TimeToStruct(TimeGMT(), g);
   int m=g.hour*60+g.min;
   return (m>=390 && m<=690) || (m>=780 && m<=960);
}
int FeedNow() { return InFastWindow() ? MathMin(FastFeedSec,FeedSec) : FeedSec; }

string PsymOf(const string bsym) { for(int k=0;k<7;k++) if(BrokerSym(NAMES[k])==bsym) return NAMES[k]; return ""; }

ulong FindOrder(const string id)
{
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      ulong tk=OrderGetTicket(i);
      if(tk==0 || OrderGetInteger(ORDER_MAGIC)!=MagicNumber) continue;
      if(OrderGetString(ORDER_COMMENT)=="Pult "+id) return tk;
   }
   return 0;
}
bool HasPosition(const string id)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(!PositionSelectByTicket(tk) || PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      if(PositionGetString(POSITION_COMMENT)=="Pult "+id) return true;
   }
   return false;
}
bool HadDealToday(const string id)
{
   MqlDateTime d; TimeToStruct(TimeCurrent(), d); d.hour=0; d.min=0; d.sec=0;
   if(!HistorySelect(StructToTime(d), TimeCurrent()+60)) return false;
   for(int i=HistoryDealsTotal()-1;i>=0;i--)
   {
      ulong tk=HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(tk,DEAL_MAGIC)!=MagicNumber) continue;
      if(HistoryDealGetInteger(tk,DEAL_ENTRY)==DEAL_ENTRY_IN && HistoryDealGetString(tk,DEAL_COMMENT)=="Pult "+id) return true;
   }
   return false;
}
void DeletePending(const string id)
{
   ulong tk=FindOrder(id);
   if(tk>0 && trade.OrderDelete(tk)) { Print(id," отложенный ордер снят"); GlobalVariableDel("PULTX_"+(string)tk); }
}

// ---------- сопровождение позиций и отложенных ордеров (каждые 5 с) ----------
void ManageTrades()
{
   // 1) Тип C: стоп в БУ, когда цена прошла 50% пути к цели
   if(MoveToBE)
      for(int i=PositionsTotal()-1;i>=0;i--)
      {
         ulong tk=PositionGetTicket(i);
         if(!PositionSelectByTicket(tk) || PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
         string cm=PositionGetString(POSITION_COMMENT);
         if(StringFind(cm,"_C")<0) continue;
         string sym=PositionGetString(POSITION_SYMBOL);
         bool isBuy=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY;
         double op=PositionGetDouble(POSITION_PRICE_OPEN), sl=PositionGetDouble(POSITION_SL), tp=PositionGetDouble(POSITION_TP);
         if(tp<=0) continue;
         double be=op+0.5*(tp-op);
         int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
         double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
         if(isBuy && bid>=be && sl<op-SymbolInfoDouble(sym,SYMBOL_POINT)) { if(trade.PositionModify(tk,NormalizeDouble(op,dg),tp)) Print(cm," стоп в БУ (",DoubleToString(op,dg),")"); }
         if(!isBuy && ask<=be && (sl>op+SymbolInfoDouble(sym,SYMBOL_POINT) || sl==0)) { if(trade.PositionModify(tk,NormalizeDouble(op,dg),tp)) Print(cm," стоп в БУ (",DoubleToString(op,dg),")"); }
      }
   // 2) отложенные ордера
   for(int i=OrdersTotal()-1;i>=0;i--)
   {
      ulong tk=OrderGetTicket(i);
      if(tk==0 || OrderGetInteger(ORDER_MAGIC)!=MagicNumber) continue;
      string cm=OrderGetString(ORDER_COMMENT), sym=OrderGetString(ORDER_SYMBOL);
      long ty=OrderGetInteger(ORDER_TYPE);
      double tp=OrderGetDouble(ORDER_TP);
      double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
      bool isBuy=(ty==ORDER_TYPE_BUY_STOP||ty==ORDER_TYPE_BUY_LIMIT);
      // Тип C stop: экстремум обновился (цена ушла за него) — снимаем, Пульт выставит новый уровень
      if(ty==ORDER_TYPE_BUY_STOP || ty==ORDER_TYPE_SELL_STOP)
      {
         double ext=GlobalVariableCheck("PULTX_"+(string)tk) ? GlobalVariableGet("PULTX_"+(string)tk) : 0;
         if(ext>0 && ((isBuy && bid<ext) || (!isBuy && ask>ext))) { if(trade.OrderDelete(tk)) { Print(cm," экстремум обновился — ордер снят, жду новый уровень"); GlobalVariableDel("PULTX_"+(string)tk); } continue; }
         // другая позиция той же группы и стороны уже открыта — лишний ордер снимаем
         string ps=PsymOf(sym);
         if(OneIdeaPerGroup && ps!="" && GroupBusy(GroupOf(ps),isBuy)) { if(trade.OrderDelete(tk)) { Print(cm," в группе уже есть позиция — ордер снят"); GlobalVariableDel("PULTX_"+(string)tk); } }
      }
      // Тип A лимит: цель достигнута без нас — ордер больше не нужен
      if(tp>0 && (ty==ORDER_TYPE_BUY_LIMIT||ty==ORDER_TYPE_SELL_LIMIT) && ((isBuy && bid>=tp) || (!isBuy && ask<=tp)))
         { if(trade.OrderDelete(tk)) Print(cm," цель достигнута без входа — лимит снят"); }
   }
}

// ---------- свечи брокера -> Пульт ----------
string BarsLine(const string psym,const string sym,ENUM_TIMEFRAMES tf,const string tfn,int cnt,int off)
{
   MqlRates r[]; ArraySetAsSeries(r,false);
   int n=CopyRates(sym,tf,0,cnt,r);
   if(n<=0) return "";
   int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   string s=psym+"|"+tfn+"|";
   for(int i=0;i<n;i++)
   {
      if(i>0) s+=";";
      s+=IntegerToString((long)r[i].time-off)+","+DoubleToString(r[i].open,dg)+","+DoubleToString(r[i].high,dg)+","
         +DoubleToString(r[i].low,dg)+","+DoubleToString(r[i].close,dg);
   }
   return s+"\n";
}

void SendFeed()
{
   if(!FeedEnabled || FeedKey=="") return;
   datetime now=TimeLocal();
   if(now-lastFeed<FeedNow()) return;
   bool full=(now-lastFull>=3600);          // раз в час — полная история, иначе последние бары
   int off=(int)MathRound((double)(TimeTradeServer()-TimeGMT())/900.0)*900;
   string body="FEED1\n";
   for(int k=0;k<7;k++)
   {
      string sym=BrokerSym(NAMES[k]);
      if(sym=="" || !SymbolSelect(sym,true)) continue;
      body+=BarsLine(NAMES[k],sym,PERIOD_M5,"M5",full?3456:8,off);
      body+=BarsLine(NAMES[k],sym,PERIOD_H1,"H1",full?960:3,off);
      body+=BarsLine(NAMES[k],sym,PERIOD_D1,"D1",full?60:2,off);
   }
   char data[], res[]; string rh;
   int len=StringToCharArray(body,data,0,WHOLE_ARRAY,CP_UTF8);
   if(len>0) ArrayResize(data,len-1);
   string hdr="Content-Type: text/plain\r\nx-pult-key: "+FeedKey+"\r\n";
   ResetLastError();
   int code=WebRequest("POST",FeedURL,hdr,15000,data,res,rh);
   lastFeed=now;
   if(code==200) { if(full) { lastFull=now; Print("Пульт: полная история свечей отправлена"); } }
   else Print("Пульт: свечи не приняты (",code,", ошибка ",GetLastError(),") ",CharArrayToString(res,0,80));
}

void OnTimer()
{
   SendFeed();
   if(TradeEnabled) ManageTrades();
   datetime nowT=TimeLocal();
   if(nowT-lastPoll<PollSec) return;
   lastPoll=nowT;
   char post[], res[]; string rh;
   ResetLastError();
   int code=WebRequest("GET", SignalsURL, "", 8000, post, res, rh);
   if(code!=200)
   { Print("Сайт Пульта не ответил (", code, ", ошибка ", GetLastError(), "). Добавьте URL в Сервис → Настройки → Советники → WebRequest."); return; }
   string lines[];
   string seen="|";
   int n=StringSplit(CharArrayToString(res,0,WHOLE_ARRAY,CP_UTF8),'\n',lines);
   if(n<2 || lines[0]!="PULT1") { Print("Неожиданный ответ сайта"); return; }
   datetime nowUtc=(datetime)StringToInteger(lines[1]);
   for(int i=2;i<n;i++)
   {
      string f[];
      int nf=StringSplit(lines[i],'|',f);
      if(nf<8) continue;
      seen+=(f[7]=="wait"?StringSubstr(f[0],0,StringLen(f[0])-1):f[0])+"|";
      if(f[7]=="wait") { if(PendEnabled) HandleWait(f[0],f[1],f[2],StringToDouble(f[4]),StringToDouble(f[5]),StringToDouble(f[6]),(nf>9?StringToDouble(f[9]):0)); continue; }
      Process(f[0],f[1],f[2],(datetime)StringToInteger(f[3]),StringToDouble(f[4]),StringToDouble(f[5]),StringToDouble(f[6]),f[7],nowUtc,(nf>10?(datetime)StringToInteger(f[10]):0));
   }
   // stop-ордера Типа C, которых Пульт больше не ждёт (скип / сделка закрыта), снимаем
   if(TradeEnabled)
      for(int i=OrdersTotal()-1;i>=0;i--)
      {
         ulong tk=OrderGetTicket(i);
         if(tk==0 || OrderGetInteger(ORDER_MAGIC)!=MagicNumber) continue;
         long ty=OrderGetInteger(ORDER_TYPE);
         if(ty!=ORDER_TYPE_BUY_STOP && ty!=ORDER_TYPE_SELL_STOP) continue;
         string cm=OrderGetString(ORDER_COMMENT);
         if(StringLen(cm)<6) continue;
         string oid=StringSubstr(cm,5);
         if(StringFind(seen,"|"+oid+"|")<0) { if(trade.OrderDelete(tk)) { Print(oid," Пульт больше не ждёт вход — ордер снят"); GlobalVariableDel("PULTX_"+(string)tk); } }
      }
}

double LotsFor(const string sym,const bool isBuy,const double price,const double sl)
{
   double loss=0;
   if(!OrderCalcProfit(isBuy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,sym,1.0,price,sl,loss) || loss>=0) return 0;
   double riskMoney=AccountInfoDouble(ACCOUNT_BALANCE)*RiskPercent/100.0;
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP), vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
   double lots=MathFloor(riskMoney/MathAbs(loss)/step)*step;
   if(lots<vmin) return 0;
   return MathMin(lots,vmax);
}

void PlaceLimitA(const string gv,const string id,const string sym,const bool isBuy,const double ref,const double dSL,const double dTP,const datetime endUtc)
{
   int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   double sl=NormalizeDouble(isBuy?ref-dSL:ref+dSL,dg), tk=NormalizeDouble(isBuy?ref+dTP:ref-dTP,dg);
   double lots=LotsFor(sym,isBuy,ref,sl);
   if(lots<=0) { Done(gv,id+" пропуск: лот для лимита не посчитан"); return; }
   int off=(int)(TimeTradeServer()-TimeGMT());
   datetime exp=(endUtc>0)?(datetime)((long)endUtc+off):TimeCurrent()+6*3600;
   if(exp<=TimeCurrent()+120) { Done(gv,id+" пропуск: время сделки вышло"); return; }
   trade.SetTypeFillingBySymbol(sym);
   bool ok=isBuy?trade.BuyLimit(lots,ref,sym,sl,tk,ORDER_TIME_SPECIFIED,exp,"Pult "+id):trade.SellLimit(lots,ref,sym,sl,tk,ORDER_TIME_SPECIFIED,exp,"Pult "+id);
   if(ok) Done(gv,id+": цена ушла — лимит на откат к "+DoubleToString(ref,dg)+" лот "+DoubleToString(lots,2)+" до конца сделки");
   else Print(id," лимит не принят: ",trade.ResultRetcode()," ",trade.ResultRetcodeDescription());
}

// Тип C: stop-ордер на уровне 20% длины выноса. id вида ДАТА_СИМВОЛ_Cw; реальный id (без w) станет сигналом, когда вход случится.
void HandleWait(const string idw,const string psym,const string side,const double entry,const double stop,const double tp,const double ext)
{
   string id=StringSubstr(idw,0,StringLen(idw)-1);
   if(GlobalVariableCheck("PULT_"+id)) return;
   if(HasPosition(id) || HadDealToday(id)) return;
   if(!TradeEnabled) return;
   if(DemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO) return;
   string sym=BrokerSym(psym);
   if(sym=="" || !SymbolSelect(sym,true)) return;
   bool isBuy=(side=="long");
   int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   double pe=NormalizeDouble(entry,dg), ps=NormalizeDouble(stop,dg), pt=NormalizeDouble(tp,dg);
   double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
   if(ext>0 && ((isBuy && bid<ext) || (!isBuy && ask>ext))) return;       // экстремум ещё обновляется — ждём новый уровень
   if(isBuy ? (ask>=pe) : (bid<=pe)) return;                              // уровень уже пройден — дальше работает обычный сигнал
   ulong tk=FindOrder(id);
   if(tk>0)
   {
      double po=OrderGetDouble(ORDER_PRICE_OPEN), pl=OrderGetDouble(ORDER_SL), pp=OrderGetDouble(ORDER_TP);
      double pt0=SymbolInfoDouble(sym,SYMBOL_POINT);
      if(MathAbs(po-pe)<pt0 && MathAbs(pl-ps)<pt0 && MathAbs(pp-pt)<pt0) return;
      if(!trade.OrderDelete(tk)) return;
      GlobalVariableDel("PULTX_"+(string)tk);
   }
   else
   {
      int entries,losses; TodayStats(entries,losses);
      if(entries>=MaxEntriesDay || losses>=StopAfterLosses) return;
      if(OneIdeaPerGroup && GroupBusy(GroupOf(psym),isBuy)) return;
   }
   double lots=LotsFor(sym,isBuy,pe,ps);
   if(lots<=0) return;
   trade.SetTypeFillingBySymbol(sym);
   datetime exp=TimeCurrent()+2*3600;
   bool ok=isBuy?trade.BuyStop(lots,pe,sym,ps,pt,ORDER_TIME_SPECIFIED,exp,"Pult "+id):trade.SellStop(lots,pe,sym,ps,pt,ORDER_TIME_SPECIFIED,exp,"Pult "+id);
   if(ok)
   {
      ulong nt=trade.ResultOrder();
      if(ext>0) GlobalVariableSet("PULTX_"+(string)nt,ext);
      PrintFormat("%s: %s STOP %s лот %.2f на %s SL %s TP %s",id,isBuy?"BUY":"SELL",sym,lots,DoubleToString(pe,dg),DoubleToString(ps,dg),DoubleToString(pt,dg));
   }
   else Print(id," stop-ордер не принят: ",trade.ResultRetcode()," ",trade.ResultRetcodeDescription());
}

void Process(const string id,const string psym,const string side,const datetime tUtc,
             const double entry,const double stop,const double tp,const string status,const datetime nowUtc,const datetime endUtc=0)
{
   string gv="PULT_"+id;
   if(status!="open") DeletePending(id);     // сделка закрыта по сигналу Пульта — висящий ордер не нужен
   if(GlobalVariableCheck(gv)) return;
   if(status!="open") { Done(gv,""); return; }
   if(HasPosition(id)) { Done(gv,id+": позиция уже открыта ордером"); return; }
   if(FindOrder(id)>0) return;                 // отложенный ордер ещё ждёт исполнения
   if(HadDealToday(id)) { Done(gv,id+": вход уже был"); return; }
   long ageMin=(long)(nowUtc-tUtc)/60;
   if(ageMin<0) return;
   if(ageMin>MaxSignalAgeMin) { Done(gv,id+" пропуск: сигналу "+(string)ageMin+" мин"); return; }
   if(DemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO) { Done(gv,id+" пропуск: не демо-счёт"); return; }

   string sym=BrokerSym(psym);
   if(sym=="" || !SymbolSelect(sym,true)) { Done(gv,id+" нет символа у брокера: "+psym); return; }
   bool isBuy=(side=="long");
   double dSL=MathAbs(entry-stop), dTP=MathAbs(tp-entry);
   if(dSL<=0) { Done(gv,""); return; }

   int entries,losses; TodayStats(entries,losses);
   if(entries>=MaxEntriesDay)  { Done(gv,id+" пропуск: уже "+(string)entries+" входа сегодня"); return; }
   if(losses>=StopAfterLosses) { Done(gv,id+" пропуск: уже "+(string)losses+" стопа сегодня"); return; }
   if(OneIdeaPerGroup && GroupBusy(GroupOf(psym),isBuy)) { Done(gv,id+" пропуск: в группе уже есть позиция в ту же сторону"); return; }

   // цена входа у брокера = открытие M5-свечи сигнала
   int off=(int)(TimeTradeServer()-TimeGMT());
   datetime bar=(datetime)(((long)(tUtc+off)/300)*300);
   double op[];
   if(CopyOpen(sym,PERIOD_M5,bar,1,op)!=1) { Print(id," нет M5-данных брокера, повторю"); return; }
   double ref=op[0];
   double price=isBuy?SymbolInfoDouble(sym,SYMBOL_ASK):SymbolInfoDouble(sym,SYMBOL_BID);
   if(MathAbs(price-ref)>MaxDriftOfStop*dSL)
   {
      // Тип A: цена ушла в нашу сторону — ставим лимит на откат к цене сигнала (до конца сделки 22:00 Рига)
      bool fav=isBuy?(price>ref):(price<ref);
      if(LimitOnMissA && TradeEnabled && fav && StringFind(id,"_A")>0) { PlaceLimitA(gv,id,sym,isBuy,ref,dSL,dTP,endUtc); return; }
      Done(gv,id+" пропуск: цена ушла от входа ("+DoubleToString(price,2)+" против "+DoubleToString(ref,2)+")"); return;
   }

   int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   double sl=NormalizeDouble(isBuy?ref-dSL:ref+dSL,dg), tk=NormalizeDouble(isBuy?ref+dTP:ref-dTP,dg);
   if((isBuy&&(price<=sl||price>=tk))||(!isBuy&&(price>=sl||price<=tk))) { Done(gv,id+" пропуск: цена вне стоп/тейк"); return; }

   double loss=0;
   if(!OrderCalcProfit(isBuy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,sym,1.0,price,sl,loss) || loss>=0) { Print(id," не посчитан лот"); return; }
   double riskMoney=AccountInfoDouble(ACCOUNT_BALANCE)*RiskPercent/100.0;
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP), vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
   double lots=MathFloor(riskMoney/MathAbs(loss)/step)*step;
   if(lots<vmin) { Done(gv,id+" пропуск: лот меньше минимального"); return; }
   lots=MathMin(lots,vmax);

   PrintFormat("%s: %s %s лот %.2f вход~%s SL %s TP %s риск %.2f",id,isBuy?"BUY":"SELL",sym,lots,
               DoubleToString(price,dg),DoubleToString(sl,dg),DoubleToString(tk,dg),riskMoney);
   if(!TradeEnabled) { Done(gv,"TradeEnabled=false — только журнал"); return; }
   trade.SetTypeFillingBySymbol(sym);
   bool ok=isBuy?trade.Buy(lots,sym,0,sl,tk,"Pult "+id):trade.Sell(lots,sym,0,sl,tk,"Pult "+id);
   if(ok) GlobalVariableSet(gv,1);
   else Print(id," ошибка: ",trade.ResultRetcode()," ",trade.ResultRetcodeDescription());
}
