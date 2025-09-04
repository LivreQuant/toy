// frontend_dist/packages/api/src/types/fund-types.ts
import { FundProfile, CreateFundProfileRequest, UpdateFundProfileRequest } from '@trading-app/types-core';

export interface CreateFundProfileResponse {
  success: boolean;
  fundId?: string;
  error?: string;
}

export interface GetFundProfileResponse {
  success: boolean;
  fund?: FundProfile;
  error?: string;
}

export interface UpdateFundProfileResponse {
  success: boolean;
  error?: string;
}

export { FundProfile, CreateFundProfileRequest, UpdateFundProfileRequest };