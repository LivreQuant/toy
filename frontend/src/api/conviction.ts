// src/api/conviction.ts
import { HttpClient } from './http-client';
import { ConvictionData } from '../types';

export interface ConvictionSubmissionRequest {
  convictions: ConvictionData[];
  researchFile?: File;
  notes?: string;
}

export interface ConvictionCancellationRequest {
  convictionIds: string[];
  researchFile?: File;
  notes?: string;
}

export interface EncodedConvictionSubmissionRequest {
  convictions: string; // Encoded fingerprint string
  researchFile?: string; // Encoded research file fingerprint string
  notes?: string;
}

export interface EncodedConvictionCancellationRequest {
  convictionIds: string; // Encoded fingerprint string
  researchFile?: string; // Encoded research file fingerprint string
  notes?: string;
}

// Keep the rest of the file unchanged
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


export class ConvictionsApi {
  private client: HttpClient;

  constructor(client: HttpClient) {
    this.client = client;
  }

  async submitConvictions(submissionData: ConvictionSubmissionRequest): Promise<BatchConvictionResponse> {
    const formData = new FormData();
    
    // Add the convictions as a JSON blob
    formData.append('convictions', JSON.stringify(submissionData.convictions));
    
    // Add research file if provided
    if (submissionData.researchFile) {
      formData.append('researchFile', submissionData.researchFile);
    }
    
    // Add notes if provided
    if (submissionData.notes) {
      formData.append('notes', submissionData.notes);
    }

    return this.client.postMultipart<BatchConvictionResponse>('/convictions/submit', formData);
  }

  async cancelConvictions(cancellationData: ConvictionCancellationRequest): Promise<BatchCancelResponse> {
    const formData = new FormData();
    
    // Add the conviction IDs as a JSON array
    formData.append('convictionIds', JSON.stringify(cancellationData.convictionIds));
    
    // Add research file if provided
    if (cancellationData.researchFile) {
      formData.append('researchFile', cancellationData.researchFile);
    }
    
    // Add notes if provided
    if (cancellationData.notes) {
      formData.append('notes', cancellationData.notes);
    }

    return this.client.postMultipart<BatchCancelResponse>('/convictions/cancel', formData);
  }

  // New encoded fingerprint methods
  async submitConvictionsEncoded(submissionData: EncodedConvictionSubmissionRequest): Promise<BatchConvictionResponse> {
    return this.client.post<BatchConvictionResponse>('/convictions/encoded_submit', {
      convictions: submissionData.convictions,
      researchFile: submissionData.researchFile,
      notes: submissionData.notes
    });
  }

  async cancelConvictionsEncoded(cancellationData: EncodedConvictionCancellationRequest): Promise<BatchCancelResponse> {
    return this.client.post<BatchCancelResponse>('/convictions/encoded_cancel', {
      convictionIds: cancellationData.convictionIds,
      researchFile: cancellationData.researchFile,
      notes: cancellationData.notes
    });
  }
}