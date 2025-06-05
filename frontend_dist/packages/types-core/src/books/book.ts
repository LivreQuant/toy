
  
import { ConvictionModelConfig } from '../convictions/config';

  // packages/types-core/src/books/book.ts
  export interface Book {
    bookId: string;
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