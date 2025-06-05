import { HttpClient } from './http-client';
import { FundProfile, CreateFundProfileRequest, UpdateFundProfileRequest } from '../types';
export declare class FundApi {
    private client;
    constructor(client: HttpClient);
    /**
     * Creates a new fund profile
     */
    createFundProfile(fundData: CreateFundProfileRequest): Promise<{
        success: boolean;
        fundId?: string;
        error?: string;
    }>;
    /**
     * Retrieves the current user's fund profile
     */
    getFundProfile(): Promise<{
        success: boolean;
        fund?: FundProfile;
        error?: string;
    }>;
    /**
     * Updates an existing fund profile
     */
    updateFundProfile(updates: UpdateFundProfileRequest): Promise<{
        success: boolean;
        error?: string;
    }>;
}
