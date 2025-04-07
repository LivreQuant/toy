// src/api/order.ts
import { HttpClient } from './http-client';

export type OrderSide = 'BUY' | 'SELL';
export type OrderType = 'MARKET' | 'LIMIT';
export type OrderStatus = 'NEW' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELED' | 'REJECTED';

export interface SubmitOrderRequest {
  symbol: string;
  side: OrderSide;
  quantity: number;
  price?: number;
  type: OrderType;
  requestId?: string;  // For idempotency
}

export interface SubmitOrderResponse {
  success: boolean;
  orderId: string;
  errorMessage?: string;
}

export interface OrderStatusResponse {
  status: OrderStatus;
  filledQuantity: number;
  avgPrice: number;
  errorMessage?: string;
}

export class OrdersApi {
  private client: HttpClient;

  constructor(client: HttpClient) {
    this.client = client;
  }

  async submitOrder(order: SubmitOrderRequest): Promise<SubmitOrderResponse> {
    return this.client.post<SubmitOrderResponse>('/orders/submit', order);
  }

  async cancelOrder(orderId: string): Promise<{ success: boolean }> {
    return this.client.post<{ success: boolean }>('/orders/cancel', { orderId });
  }
}