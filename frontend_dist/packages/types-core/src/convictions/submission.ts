
import { ConvictionData } from './conviction-data';

  // packages/types-core/src/convictions/submission.ts
  export interface ConvictionSubmissionRequest {
    bookId: string;
    convictions: ConvictionData[];
    researchFile?: File;
    notes?: string;
  }
  
  export interface ConvictionCancellationRequest {
    bookId: string;
    convictionIds: string[];
    researchFile?: File;
    notes?: string;
  }
  
  export interface EncodedConvictionSubmissionRequest {
    bookId: string;
    convictions: string;
    researchFile?: string;
    notes?: string;
  }
  
  export interface EncodedConvictionCancellationRequest {
    bookId: string;
    convictionIds: string;
    researchFile?: string;
    notes?: string;
  }