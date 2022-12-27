from AlgorithmImports import *
from datetime import timedelta
from QuantConnect.Data.Custom.CBOE import *

class TransdimensionalModulatedProcessor(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2017, 10, 1)  # Set Start Date
        self.SetEndDate(2020, 10, 1) #set end date
        self.SetCash(100000)  # Set Strategy Cash
        self.equity = self.AddEquity("SPY", Resolution.Minute) #add spy 
        self.equity.SetDataNormalizationMode(DataNormalizationMode.raw) #sets data normalization mode
        self.symbol = self.equity.Symbol #idk what this does
        self.vix = self.AddData(CBOE, "VIX").Symbol #stores symbol
        self.rank = 0 #initialize volatility
        self.contract = str() 
        self.contractsAdded = set()
        self.DaysBeforeExp = 2 #initialize when we are opting out of options before they expire
        self.DTE = 25 #target days until exp
        self.OTM = 0.01 #put option out of money by 0.01 percent goal
        self.lookBackIV = 150 #how many days we look back
        self.IVlvl = 0.5 #signal line
        self.percentage = 0.9 #90 percent portfolio to spy
        self.optionsAlloc = 90 #how many options we buy compared to shares of underlying asset

        self.Schedule.On(self.dataRules.EveryDay(self.Symbol), \
                                                self.TimeRules.AfterMarketOpen(self.symbol, 30), \
                                                self.Plotting)
        self.Schedule.On(self.dataRules.EveryDay(self.Symbol), \
                                                self.TimeRules.AfterMarketOpen(self.symbol, 30), \
                                                self.VIXRank)
        self.SetWarmup(timedelta(self.lookBackIV))

    def VIXRank(self):
        history = self.History(CBOE, self.vix, self.lookBackIV, Resolution.Daily)
        self.rank = ((self.Securities[self.vix].Price - min(history[:-1]["low"])) / max(history[:-1]["high"]) - min(history[:-1]["low"]))



    def OnData(self, data: Slice):
        if self.IsWarmingUp:
            return

        if not self.Portfolio[self.symbol].Invested:
            self.SetHoldings(self.symbol, self.percentage)

        if self.rank > self.IVlvl:
            self.BuyPut(data)

        if self.contract:
            if (self.contract.ID.date - self.time) <= timedelta(self.DaysBeforeExp):
                self.Liquidate(self.contract)
                self.log("Closed: too close to expiration date")
                self.contract = str()


    def BuyPut(self, data):
        if self.contract == str():
            self.contract = self.OptionsFilter(data)
            return
        elif not self.Portfolio[self.contract].Invested and data.ContainsKey(self.contract):
            self.Buy(self.contract, round(self.Portfolio[self.symbol].Quantity / self.optionsAlloc))

    def OptionsFilter(self, data):
        contracts = self.OptionChainProvider.GetOptionContractList(self.symbol, data.Time)
        self.underlyingPrice = self.Securities[self.symbol].Price
        OTMputs = [i for i in contracts if i.ID.OptionRight == OptionRight.Put and 
                                            self.underlyingPrice - i.ID.StrikePrice > self.OTM * self.underlyingPrice and
                                            self.DTE - 8 < (i.ID.Date - data.Time).days < self.DTE + 8] 
        if len(OTMputs) > 0:
            contract = sorted(sorted(OTMputs, key = lambda x: abs((x.ID.Date - self.Time).days - self.DTE)),
                                                    key = lambda x: self.underlyingPrice - x.ID.StrikePrice)[0]
            if contract not in self.contractsAdded:
                self.contractsAdded.add(contract)
                self.AddOptionContract(contract, Resolution.Minute)
            return contract 
        else:
            return str()

    def Plotting(self):
        self.Plot("Vol Chart", "Rank", self.rank)
        self.Plot("Vol Chart", "lvl", self.IVlvl)
        self.Plot("Data Chart", self.symbol, self.Securities[self.symbol].Close)

        optionInvested = [x.key for x in self.Portfolio if x.Value.Invested and x.Value.Type == SecurityType.Option]
        if optionInvested:
            self.Plot("Data Chart", "Strike", optionInvested[0].ID.StrikePrice)

    def OnOrderEvent(self, orderEvent):
        self.Log(str(OrderEvent))
