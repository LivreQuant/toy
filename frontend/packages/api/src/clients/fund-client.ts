// frontend_dist/packages/api/src/clients/fund-client.ts
import { BaseApiClient } from '../core/base-client';
import {
  CreateFundProfileRequest,
  UpdateFundProfileRequest,
  CreateFundProfileResponse,
  GetFundProfileResponse,
  UpdateFundProfileResponse
} from '../types/fund-types';

export class FundClient extends BaseApiClient {
  /**
   * Creates a new fund profile
   */
  async createFundProfile(fundData: CreateFundProfileRequest): Promise<CreateFundProfileResponse> {
    return this.post('/funds', fundData);
  }

  /**
   * Retrieves the current user's fund profile
   */
  async getFundProfile(): Promise<GetFundProfileResponse> {
    return this.get('/funds');
  }

  /**
   * Updates an existing fund profile
   */
  async updateFundProfile(updates: UpdateFundProfileRequest): Promise<UpdateFundProfileResponse> {
    return this.put('/funds', updates);
  }
}