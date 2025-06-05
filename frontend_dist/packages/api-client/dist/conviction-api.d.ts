import { HttpClient } from './http-client';
import { ConvictionData } from '../types';
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
export declare class ConvictionsApi {
    private client;
    constructor(client: HttpClient);
    submitConvictions(submissionData: ConvictionSubmissionRequest): Promise<BatchConvictionResponse>;
    cancelConvictions(cancellationData: ConvictionCancellationRequest): Promise<BatchCancelResponse>;
    submitConvictionsEncoded(submissionData: EncodedConvictionSubmissionRequest): Promise<BatchConvictionResponse>;
    cancelConvictionsEncoded(cancellationData: EncodedConvictionCancellationRequest): Promise<BatchCancelResponse>;
}
