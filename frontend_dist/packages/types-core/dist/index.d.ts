export declare enum LogLevel {
    DEBUG = 0,
    INFO = 1,
    WARN = 2,
    ERROR = 3,
    NONE = 4
}
export interface LoggerConfig {
    minLevel: LogLevel;
    structured: boolean;
    includeTimestamp: boolean;
    environment: 'development' | 'production' | 'test';
    additionalMetadata?: Record<string, any>;
}
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
export interface ConvictionData {
    instrumentId?: string;
    participationRate?: 'LOW' | 'MEDIUM' | 'HIGH';
    tag?: string;
    convictionId?: string;
    side?: 'BUY' | 'SELL' | 'CLOSE';
    score?: number;
    quantity?: number;
    zscore?: number;
    targetPercent?: number;
    targetNotional?: number;
    [key: string]: string | number | undefined;
}
export interface ConvictionSubmissionRequest {
    bookId: string;
    convictions: ConvictionData[];
    researchFile?: File;
    notes?: string;
}
export interface ConvictionCancellationRequest {
    bookId: string;
    convictionIds: string[];
    researchFile?: File;
    notes?: string;
}
export interface EncodedConvictionSubmissionRequest {
    bookId: string;
    convictions: string;
    researchFile?: string;
    notes?: string;
}
export interface EncodedConvictionCancellationRequest {
    bookId: string;
    convictionIds: string;
    researchFile?: string;
    notes?: string;
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
