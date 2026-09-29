//+------------------------------------------------------------------+
//| PultBridge.mq5 — исполнитель сигналов «Пульта входа» (ДЕМО)       |
//| Сам ничего не анализирует: раз в PollSec секунд читает сигналы     |
//| с сайта Пульта и открывает сделку с риском RiskPercent % баланса.  |
//| Стоп и тейк переносятся как РАССТОЯНИЯ от цены входа сигнала.      |
//| По умолчанию TradeEnabled=false — только пишет решения в журнал.   |
//+------------------------------------------------------------------+
#property copyright "Trading Pride"
#property version   "1.00"
#include <Trade/Trade.mqh>

input string SignalsURL      = "https://trading-pride-three.vercel.app/api/signals";
input bool   TradeEnabled    = false;   // false = только журнал, без сделок
input bool   DemoOnly        = true;    // не торговать на реальном счёте
input double RiskPercent     = 1.0;     // риск на сделку, % баланса
input int    PollSec         = 30;
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
   EventSetTimer(PollSec);
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

void OnTimer()
{
   char post[], res[]; string rh;
   ResetLastError();
   int code=WebRequest("GET", SignalsURL, "", 8000, post, res, rh);
   if(code!=200)
   { Print("Сайт Пульта не ответил (", code, ", ошибка ", GetLastError(), "). Добавьте URL в Сервис → Настройки → Советники → WebRequest."); return; }
   string lines[];
   int n=StringSplit(CharArrayToString(res,0,WHOLE_ARRAY,CP_UTF8),'\n',lines);
   if(n<2 || lines[0]!="PULT1") { Print("Неожиданный ответ сайта"); return; }
   datetime nowUtc=(datetime)StringToInteger(lines[1]);
   for(int i=2;i<n;i++)
   {
      string f[];
      if(StringSplit(lines[i],'|',f)<8) continue;
      Process(f[0],f[1],f[2],(datetime)StringToInteger(f[3]),StringToDouble(f[4]),StringToDouble(f[5]),StringToDouble(f[6]),f[7],nowUtc);
   }
}

void Process(const string id,const string psym,const string side,const datetime tUtc,
             const double entry,const double stop,const double tp,const string status,const datetime nowUtc)
{
   string gv="PULT_"+id;
   if(GlobalVariableCheck(gv)) return;
   if(status!="open") { Done(gv,""); return; }
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
   if(MathAbs(price-ref)>MaxDriftOfStop*dSL) { Done(gv,id+" пропуск: цена ушла от входа ("+DoubleToString(price,2)+" против "+DoubleToString(ref,2)+")"); return; }

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
