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
  status: string;
  activeAt: number;
  expireAt: number;
  
  regions: string[];
  markets: string[];
  instruments: string[];
  investmentApproaches: string[];
  investmentTimeframes: string[];
  sectors: string[];
  positionTypes: {
    long: boolean;
    short: boolean;
  };
  initialCapital: number;
}

export interface BookRequest {
  name: string;
  regions: string[];
  markets: string[];
  instruments: string[];
  investmentApproaches: string[];
  investmentTimeframes: string[];
  sectors: string[];
  positionTypes: {
    long: boolean;
    short: boolean;
  };
  initialCapital: number;
}

export interface TeamMember {
  id: string;
  firstName: string;
  lastName: string;
  role: string;
  yearsExperience?: string;
  education?: string;
  currentEmployment?: string;
  investmentExpertise?: string;
  birthDate?: string;
  linkedin?: string;
}

export interface FundProfile {
  id?: string;
  userId?: string;
  fundName: string;
  legalStructure?: string;
  location?: string;
  yearEstablished?: string;
  aumRange?: string;
  investmentStrategy?: string;
  profilePurpose?: string[];
  otherPurposeDetails?: string;
  teamMembers: TeamMember[];
  activeAt?: number;
  expireAt?: number;
}

export interface CreateFundProfileRequest {
  fundName: string;
  legalStructure?: string;
  location?: string;
  yearEstablished?: string;
  aumRange?: string;
  investmentStrategy?: string;
  profilePurpose?: string[];
  otherPurposeDetails?: string;
  teamMembers: TeamMember[];
}

export interface UpdateFundProfileRequest {
  fundName?: string;
  legalStructure?: string;
  location?: string;
  yearEstablished?: string;
  aumRange?: string;
  investmentStrategy?: string;
  profilePurpose?: string[];
  otherPurposeDetails?: string;
  teamMembers?: TeamMember[];
}