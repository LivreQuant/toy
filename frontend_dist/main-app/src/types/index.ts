// main-app/src/types/index.ts - AFTER migration
// Re-export core types for backward compatibility
export * from '@trading-app/types-core';

// Keep these UI/App-specific types in legacy
export interface UserProfile {
  id: string | number;
  username: string;
  email?: string;
}

export interface Position {
  symbol: string;
  quantity: number;
  averagePrice: number;
  marketValue: number;
  unrealizedPnl: number;
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