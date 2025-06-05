
  // packages/types-core/src/convictions/config.ts
  export interface ConvictionModelConfig {
    portfolioApproach: 'incremental' | 'target';
    targetConvictionMethod?: 'percent' | 'notional';
    incrementalConvictionMethod?: 'side_score' | 'side_qty' | 'zscore' | 'multi-horizon';
    maxScore?: number;
    horizons?: string[];
  }