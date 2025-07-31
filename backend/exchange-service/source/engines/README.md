# Conviction to Portfolio/Orders
The PM's Pure Alpha signal is now understood as a single, actionable output: the Conviction List or "Blueprint." This document specifies the desired target position for each asset (e.g., AAPL: +10.0%). This single number for each position is the result of the PM's internal process of blending their research, confidence in the thesis, and assessment of the asset's inherent risk. Other directives that define the nature of the idea, such as Urgency and Horizon, are also part of this pure signal.

PM Operational controls are the PM's self-imposed rules for their own strategy. These are knobs the PM turns to manage their own book, including their allocated AUM, personal Max Position Size, and required Days to Liquidate.

The Quant/Execution team's responsibility is to take the PM's pure signal and implement it in the market. Their domain is managing the market's reaction to their trading. They control for factors like Transaction Costs, portfolio Volatility, and Drawdown Risk.

Finally, the Firm/Risk Committee provides top-down oversight. This group sets the absolute, non-negotiable rules of the road for the entire company, such as setting Factor Exposure Limits, enforcing Firm-Wide Position Limits, and managing overall Capital Allocation.

Category,Knob,Description
"PM: Pure Alpha","Conviction List / Blueprint","The PM's final, actionable list of tickers and their desired target position weights (e.g., AAPL: +10%). This is the pure signal, which internally blends research, confidence, and risk assessment."
"PM: Pure Alpha","Direction","The intended long (BUY) or short (SELL) orientation of the position, often embedded within the sign of the target weight."
"PM: Pure Alpha","Horizon","The expected timeframe for the investment thesis to play out, which informs the strategy's intended holding period."
"PM: Pure Alpha","Urgency","A directive on how quickly the position needs to be established, informing the trading strategy."

"PM: Operational","AUM / Notional Size","The total capital the PM is responsible for managing within their specific strategy."
"PM: Operational","Max Position Size (PM Rule)","A self-imposed rule by the PM capping the size of any single position as a percentage of their own AUM."
"PM: Operational","Max Days to Liquidate","A PM-level liquidity rule based on their strategy's required nimbleness, ensuring they can exit positions within a certain timeframe."

"Quant/Execution","Transaction Cost Optimization","Modeling and minimizing the performance drag from commissions and market impact (slippage) during trade execution."
"Quant/Execution","Volatility / Tracking Error Control","Targeting a specific level of portfolio choppiness (risk) relative to the market or a benchmark."
"Quant/Execution","Drawdown Risk Management","Implementing constraints or models to limit the potential peak-to-trough loss of the portfolio's value."

"Firm/Risk Committee","Factor Exposure Limits","Setting hard caps on the firm's aggregate portfolio exposure to systematic risks (e.g., Beta, Momentum, Value)."
"Firm/Risk Committee","Firm-Wide Position Limits","An absolute, overriding limit on position size that applies to all PMs to protect the overall firm."
"Firm/Risk Committee","Overall Liquidity Constraints","Firm-level rules on what percentage of a stock's Average Daily Volume the entire firm can trade or hold."
"Firm/Risk Committee","Capital Allocation","The executive decision of how much capital each PM and strategy receives."
"Firm/Risk Committee","Regulatory & Compliance","Enforcing all non-negotiable legal and regulatory rules."

## Your Alpha Signal Taxonomy

### No Optimization Required (Direct Implementation)

V01: Target portfolio in % - Ready to trade, just apply risk overlays
Target portfolio in notional - Ready to trade, just apply risk overlays
Direction and quantity - Produces target portfolio directly

### Optimization Required (Research Signals)

Direction and magnitude - Need portfolio construction optimization
Z-score - Need full mean-variance optimization

#### OTHERS 

### Ranking/Relative Signals
ranking_signal = {
    'AAPL': 1,    # Best idea
    'GOOGL': 2,   # Second best  
    'MSFT': 3,    # Third
    'TSLA': 4     # Worst
}

### Factor Tilting
factor_tilts = {
    'momentum': 0.15,    # 15% tilt toward momentum
    'value': -0.10,      # -10% tilt away from value
    'quality': 0.05      # 5% tilt toward quality
}
