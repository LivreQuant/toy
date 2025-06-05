// src/api/fund.ts
import { HttpClient } from './http-client';
import { FundProfile, CreateFundProfileRequest, UpdateFundProfileRequest } from '@trading-app/types-core';

export class FundApi {
  private client: HttpClient;

  constructor(client: HttpClient) {
    this.client = client;
  }

  /**
   * Creates a new fund profile
   */
  async createFundProfile(fundData: CreateFundProfileRequest): Promise<{ 
    success: boolean; 
    fundId?: string; 
    error?: string 
  }> {
    return this.client.post('/funds', fundData);
  }

  /**
   * Retrieves the current user's fund profile
   */
  async getFundProfile(): Promise<{ 
    success: boolean; 
    fund?: FundProfile; 
    error?: string 
  }> {
    return this.client.get('/funds');
  }

  /**
   * Updates an existing fund profile
   */
  async updateFundProfile(updates: UpdateFundProfileRequest): Promise<{ 
    success: boolean; 
    error?: string 
  }> {
    return this.client.put(`/funds`, updates);
  }
}