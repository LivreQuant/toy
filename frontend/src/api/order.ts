// src/api/order.ts
import { HttpClient } from './http-client';

export type OrderSide = 'BUY' | 'SELL';
export type OrderType = 'MARKET' | 'LIMIT';

export interface OrderRequest {
  symbol: string;
  side: OrderSide;
  type: OrderType;
  quantity: number;
  price?: number;
  requestId?: string;
}

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

  async submitOrders(orders: OrderRequest[]): Promise<BatchOrderResponse> {
    return this.client.post<BatchOrderResponse>('/orders/submit', { orders });
  }

  async cancelOrders(orderIds: string[]): Promise<BatchCancelResponse> {
    return this.client.post<BatchCancelResponse>('/orders/cancel', { orderIds });
  }
}