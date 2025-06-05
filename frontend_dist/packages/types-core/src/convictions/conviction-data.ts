// packages/types-core/src/convictions/conviction-data.ts
export interface ConvictionData {
    instrumentId?: string;
    participationRate?: 'LOW' | 'MEDIUM' | 'HIGH';
    tag?: string;
    convictionId?: string;
    side?: 'BUY' | 'SELL' | 'CLOSE';
    score?: number;
    quantity?: number;
    zscore?: number;
    targetPercent?: number;
    targetNotional?: number;
    [key: string]: string | number | undefined;
  }
  
  