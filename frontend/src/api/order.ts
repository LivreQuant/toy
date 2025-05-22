// src/api/order.ts
import { HttpClient } from './http-client';
import { OrderData } from '../types';

export interface OrderSubmissionRequest {
  orders: OrderData[];
  researchFile?: File;
  notes?: string;
}

export interface OrderCancellationRequest {
  orderIds: [string];
  researchFile?: File;
  notes?: string;
}

export interface EncodedOrderSubmissionRequest {
  orders: string; // Encoded fingerprint string
  researchFile?: string; // Encoded research file fingerprint string
  notes?: string;
}

export interface EncodedOrderCancellationRequest {
  orderIds: string; // Encoded fingerprint string
  researchFile?: string; // Encoded research file fingerprint string
  notes?: string;
}

// Keep the rest of the file unchanged
export interface OrderResult {
  success: boolean;
  orderId?: string;
  errorMessage?: string;
}

export interface BatchOrderResponse {
  success: boolean;
  results: OrderResult[];
  errorMessage?: string;
}

export interface CancelResult {
  orderId: string;
  success: boolean;
  errorMessage?: string;
}

export interface BatchCancelResponse {
  success: boolean;
  results: CancelResult[];
  errorMessage?: string;
}


export class OrdersApi {
  private client: HttpClient;

  constructor(client: HttpClient) {
    this.client = client;
  }

  async submitOrders(submissionData: OrderSubmissionRequest): Promise<BatchOrderResponse> {
    const formData = new FormData();
    
    // Add the orders as a JSON blob
    formData.append('orders', JSON.stringify(submissionData.orders));
    
    // Add research file if provided
    if (submissionData.researchFile) {
      formData.append('researchFile', submissionData.researchFile);
    }
    
    // Add notes if provided
    if (submissionData.notes) {
      formData.append('notes', submissionData.notes);
    }

    return this.client.postMultipart<BatchOrderResponse>('/orders/submit', formData);
  }

  async cancelOrders(cancellationData: OrderCancellationRequest): Promise<BatchCancelResponse> {
    const formData = new FormData();
    
    // Add the order IDs as a JSON array
    formData.append('orderIds', JSON.stringify(cancellationData.orderIds));
    
    // Add research file if provided
    if (cancellationData.researchFile) {
      formData.append('researchFile', cancellationData.researchFile);
    }
    
    // Add notes if provided
    if (cancellationData.notes) {
      formData.append('notes', cancellationData.notes);
    }

    return this.client.postMultipart<BatchCancelResponse>('/orders/cancel', formData);
  }

  // New encoded fingerprint methods
  async submitOrdersEncoded(submissionData: EncodedOrderSubmissionRequest): Promise<BatchOrderResponse> {
    return this.client.post<BatchOrderResponse>('/orders/encoded_submit', {
      orders: submissionData.orders,
      researchFile: submissionData.researchFile,
      notes: submissionData.notes
    });
  }

  async cancelOrdersEncoded(cancellationData: EncodedOrderCancellationRequest): Promise<BatchCancelResponse> {
    return this.client.post<BatchCancelResponse>('/orders/encoded_cancel', {
      orderIds: cancellationData.orderIds,
      researchFile: cancellationData.researchFile,
      notes: cancellationData.notes
    });
  }
}