// src/types/index.ts

// You can define shared interfaces and types used across the application here.

export interface UserProfile {
  id: string | number;
  username: string;
  email?: string; // Optional email
  // Add other profile fields
}
  
// Example of a Portfolio Position type
export interface Position {
  symbol: string;
  quantity: number;
  averagePrice: number;
  marketValue: number;
  unrealizedPnl: number;
}

// Example Order type (might differ slightly from API request/response)
export interface Order {
  orderId: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  type: 'MARKET' | 'LIMIT';
  status: 'NEW' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELED' | 'REJECTED'; // Align with your backend statuses
  quantity: number;
  filledQuantity: number;
  remainingQuantity: number;
  limitPrice?: number; // Price for limit orders
  averageFillPrice?: number; // Average price if filled/partially filled
  createdAt: number; // Timestamp
  updatedAt: number; // Timestamp
}

export interface Book {
  id: string;
  userId: string;
  name: string;
  initialCapital: number;
  riskLevel: 'low' | 'medium' | 'high';
  marketFocus?: string;
  status: 'CONFIGURED' | 'ACTIVE' | 'ARCHIVED';
  tradingStrategy?: string;
  maxPositionSize?: number;
  maxTotalRisk?: number;
  createdAt: number;
  updatedAt: number;
}

export interface CreateBookRequest {
  name: string;
  parameters: Array<[string, string, string]>; // [category, subcategory, value]
}