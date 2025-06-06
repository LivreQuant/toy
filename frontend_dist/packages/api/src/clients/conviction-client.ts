// frontend_dist/packages/api/src/clients/conviction-client.ts
import { BaseApiClient } from '../core/base-client';
import {
  ConvictionSubmissionRequest,
  ConvictionCancellationRequest,
  EncodedConvictionSubmissionRequest,
  EncodedConvictionCancellationRequest,
  BatchConvictionResponse,
  BatchCancelResponse
} from '../types/conviction-types';

export class ConvictionClient extends BaseApiClient {
  async submitConvictions(submissionData: ConvictionSubmissionRequest): Promise<BatchConvictionResponse> {
    const formData = new FormData();
    
    // Add the bookId
    formData.append('bookId', submissionData.bookId);
    
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

    return this.postMultipart<BatchConvictionResponse>('/convictions/submit', formData);
  }

  async cancelConvictions(cancellationData: ConvictionCancellationRequest): Promise<BatchCancelResponse> {
    const formData = new FormData();
    
    // Add the bookId
    formData.append('bookId', cancellationData.bookId);
    
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

    return this.postMultipart<BatchCancelResponse>('/convictions/cancel', formData);
  }

  // New encoded fingerprint methods
  async submitConvictionsEncoded(submissionData: EncodedConvictionSubmissionRequest): Promise<BatchConvictionResponse> {
    return this.post<BatchConvictionResponse>('/convictions/encoded_submit', {
      bookId: submissionData.bookId,
      convictions: submissionData.convictions,
      researchFile: submissionData.researchFile,
      notes: submissionData.notes
    });
  }

  async cancelConvictionsEncoded(cancellationData: EncodedConvictionCancellationRequest): Promise<BatchCancelResponse> {
    return this.post<BatchCancelResponse>('/convictions/encoded_cancel', {
      bookId: cancellationData.bookId,
      convictionIds: cancellationData.convictionIds,
      researchFile: cancellationData.researchFile,
      notes: cancellationData.notes
    });
  }
}