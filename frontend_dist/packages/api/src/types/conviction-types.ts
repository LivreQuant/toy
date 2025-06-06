// frontend_dist/packages/api/src/types/conviction-types.ts
import { ConvictionData } from '@trading-app/types-core';

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
  convictions: string; // Encoded fingerprint string
  researchFile?: string; // Encoded research file fingerprint string
  notes?: string;
}

export interface EncodedConvictionCancellationRequest {
  bookId: string;
  convictionIds: string; // Encoded fingerprint string
  researchFile?: string; // Encoded research file fingerprint string
  notes?: string;
}

export interface ConvictionResult {
  success: boolean;
  convictionId?: string;
  errorMessage?: string;
}

export interface BatchConvictionResponse {
  success: boolean;
  results: ConvictionResult[];
  errorMessage?: string;
}

export interface CancelResult {
  convictionId: string;
  success: boolean;
  errorMessage?: string;
}

export interface BatchCancelResponse {
  success: boolean;
  results: CancelResult[];
  errorMessage?: string;
}