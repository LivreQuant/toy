// src/components/Mock/OrderDataService.ts
import { Side } from "../../../protobufs/services/orderentryservice_pb";

export interface OrderData {
  clOrderId: string;
  orderId: string;
  instrument: string;
  exchange: string;
  side: Side;
  quantity: number;
  price: number;
  orderType: string;
  status: string;
  created: Date;
  currency: string;
  fillRate?: number;
  filledQuantity?: number;
}

export class OrderDataService {
  private static mockOrders: OrderData[] = [
    {
      clOrderId: "CLO-001",
      orderId: "ORD-001",
      instrument: "AAPL",
      exchange: "SIP",
      side: Side.BUY,
      quantity: 100,
      price: 195.67,
      orderType: "LIMIT",
      status: "FILLED",
      created: new Date(Date.now() - 3600000),
      currency: "USD",
      fillRate: 1.0,
      filledQuantity: 100
    },
    {
      clOrderId: "CLO-002",
      orderId: "ORD-002",
      instrument: "MSFT",
      exchange: "SIP",
      side: Side.SELL,
      quantity: 50,
      price: 279.05,
      orderType: "LIMIT",
      status: "PARTIAL",
      created: new Date(Date.now() - 1800000),
      currency: "USD",
      fillRate: 0.5,
      filledQuantity: 25
    },
    {
      clOrderId: "CLO-003",
      orderId: "ORD-003",
      instrument: "GOOGL",
      exchange: "SIP",
      side: Side.BUY,
      quantity: 75,
      price: 128.42,
      orderType: "MARKET",
      status: "PENDING",
      created: new Date(Date.now() - 600000),
      currency: "USD"
    }
  ];

  static getOrders(): OrderData[] {
    return this.mockOrders;
  }

  static getOrderById(orderId: string): OrderData | undefined {
    return this.mockOrders.find(order => order.orderId === orderId);
  }

  static getOrderByClOrderId(clOrderId: string): OrderData | undefined {
    return this.mockOrders.find(order => order.clOrderId === clOrderId);
  }

  static addOrder(order: Omit<OrderData, 'orderId' | 'status' | 'created'>): OrderData {
    const newOrder: OrderData = {
      ...order,
      orderId: `ORD-${Math.floor(1000 + Math.random() * 9000)}`,
      status: "PENDING",
      created: new Date()
    };
    
    this.mockOrders.unshift(newOrder);
    return newOrder;
  }

  static cancelOrder(orderId: string): boolean {
    const orderIndex = this.mockOrders.findIndex(order => order.orderId === orderId);
    if (orderIndex >= 0 && this.mockOrders[orderIndex].status !== "FILLED") {
      this.mockOrders[orderIndex].status = "CANCELLED";
      return true;
    }
    return false;
  }

  static cancelOrderByClOrderId(clOrderId: string): boolean {
    const orderIndex = this.mockOrders.findIndex(order => order.clOrderId === clOrderId);
    if (orderIndex >= 0 && this.mockOrders[orderIndex].status !== "FILLED") {
      this.mockOrders[orderIndex].status = "CANCELLED";
      return true;
    }
    return false;
  }
}