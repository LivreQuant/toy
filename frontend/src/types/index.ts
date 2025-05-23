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

// Example Conviction type (might differ slightly from API request/response)
export interface ConvictionData {
  // All fields are optional during processing, but some become required for API calls
  instrumentId?: string;
  participationRate?: 'LOW' | 'MEDIUM' | 'HIGH'; // Allow number values
  tag?: string;
  convictionId?: string;
  
  // Optional depending on the conviction format
  side?: 'BUY' | 'SELL' | 'CLOSE';
  score?: number;
  quantity?: number;
  zscore?: number;
  targetPercent?: number;
  targetNotional?: number;
  
  // Allow dynamic properties for multi-horizon z-scores
  [key: string]: string | number | undefined;
}

export interface ConvictionModelConfig {
  portfolioApproach: 'incremental' | 'target';
  targetConvictionMethod?: 'percent' | 'notional';
  incrementalConvictionMethod?: 'side_score' | 'side_qty' | 'zscore' | 'multi-horizon';
  maxScore?: number;
  horizons?: string[];
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
  convictionSchema?: ConvictionModelConfig;
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
  convictionSchema?: ConvictionModelConfig;
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