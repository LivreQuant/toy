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
  // Required for all orders
  instrumentId: string;  // FIGI or other identifier
  orderId: string;       // For tracking/cancellation
  
  // Conviction (DISCRETIONARY)
  side?: 'BUY' | 'SELL' | 'CLOSE';
  quantity?: number;

  // Conviction (QUANTITATIVE)
  zscore?: number;
  
  // Execution parameters (% OF VWAP)
  participationRate?: 'LOW' | 'MEDIUM' | 'HIGH' | number;
  
  // Metadata
  category?: string;
}

export interface OrderSchemaConfig {
  convictionMethod: 'side' | 'zscore';
  includeParticipationRate: boolean;
  includeCategory: boolean;
  additionalFields?: string[];
}

export interface Book {
  bookId: string;
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
  orderSchema?: OrderSchemaConfig;
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
  orderSchema?: OrderSchemaConfig;
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