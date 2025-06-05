
  
import { ConvictionModelConfig } from '../convictions/config';

  // packages/types-core/src/books/book-request.ts
  export interface BookRequest {
    name: string;
    regions: string[];
    markets: string[];
    instruments: string[];
    investmentApproaches: string[];
    investmentTimeframes: string[];
    sectors: string[];
    positionTypes: {
      long: boolean;
      short: boolean;
    };
    convictionSchema?: ConvictionModelConfig;
    initialCapital: number;
  }