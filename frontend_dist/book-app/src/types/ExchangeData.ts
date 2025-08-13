// src/types/ExchangeData.ts
export interface ExchangeDataMessage {
    type: "exchange_data";
    deltaType: "FULL" | "DELTA";
    sequence: number;
    timestamp: number;
    data: ExchangeData;
    compressed: boolean;
    deltaEnabled: boolean;
    compressionEnabled: boolean;
    dataSavings: string;
  }
  
  export interface ExchangeData {
    updateId: string;
    timestamp: number;
    exchangeType: "EQUITIES" | "OPTIONS" | "FUTURES";
    equityData: EquityDataItem[];
    orders: OrderDataItem[];
    portfolio: PortfolioData;
    metadata: Record<string, any>;
  }
  
  export interface EquityDataItem {
    symbol: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    trade_count: number;
    vwap: number;
    exchange_type: string;
    metadata: Record<string, any>;
  }
  
  export interface OrderDataItem {
    orderId: string;
    symbol: string;
    side: "BUY" | "SELL";
    quantity: number;
    price: number;
    status: string;
    timestamp: number;
    exchange_type: string;
    metadata: Record<string, any>;
  }
  
  export interface PortfolioData {
    positions: PositionDataItem[];
    cash_balance: number;
    total_value: number;
    exchange_type: string;
    metadata: Record<string, any>;
  }
  
  export interface PositionDataItem {
    symbol: string;
    quantity: number;
    average_price: number;
    market_value: number;
    unrealized_pnl: number;
    metadata: Record<string, any>;
  }