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
  
  async getOrderStatus(orderId: string): Promise<OrderStatusResponse> {
    return this.client.get<OrderStatusResponse>(`/orders/status?orderId=${orderId}`);
  }
  
  async getOrders(): Promise<Array<{
    orderId: string;
    symbol: string;
    side: OrderSide;
    type: OrderType;
    status: OrderStatus;
    quantity: number;
    filledQuantity: number;
    price?: number;
    avgPrice: number;
    createdAt: number;
  }>> {
    // Get all orders for the current session
    return this.client.get<any[]>('/orders');
  }
}