// frontend_dist/main-app/src/services/fund/fund-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '@trading-app/auth';
import { FundClient } from '@trading-app/api';
import { FundProfile, TeamMember, CreateFundProfileRequest, UpdateFundProfileRequest } from '../../types';
import { toastService } from '../notification/toast-service';

export class FundManager {
  private logger = getLogger('FundManager');
  private fundApi: FundClient;
  private tokenManager: TokenManager;

  constructor(fundApi: FundClient, tokenManager: TokenManager) {
    this.fundApi = fundApi;
    this.tokenManager = tokenManager;
    this.logger.info('FundManager initialized');
  }

  /**
   * Creates a new fund profile
   */
  async createFundProfile(fundData: CreateFundProfileRequest): Promise<{ 
    success: boolean; 
    fundId?: string;
    error?: string; 
  }> {
    if (!this.tokenManager.isAuthenticated()) {
      toastService.error('You must be logged in to create a fund profile');
      return { success: false, error: 'Not authenticated' };
    }

    try {
      const response = await this.fundApi.createFundProfile(fundData);
      
      if (response.success && response.fundId) {
        toastService.success(`Fund "${fundData.fundName}" created successfully`);
        return { 
          success: true, 
          fundId: response.fundId 
        };
      } else {
        toastService.error(response.error || 'Failed to create fund profile');
        return { 
          success: false, 
          error: response.error || 'Unknown error'
        };
      }
    } catch (error: any) {
      this.logger.error('Fund profile creation failed', error);
      toastService.error(`Failed to create fund profile: ${error.message}`);
      return { 
        success: false, 
        error: error.message || 'Unknown error'
      };
    }
  }

    
  /**
   * Retrieves the current user's fund profile
   */
  async getFundProfile(): Promise<{ 
    success: boolean; 
    fund?: FundProfile;
    error?: string; 
  }> {
    if (!this.tokenManager.isAuthenticated()) {
      return { success: false, error: 'Not authenticated' };
    }

    try {
      const response = await this.fundApi.getFundProfile();
      
      if (response.success && response.fund) {
        // Transform the API response to match our expected FundProfile structure
        // Use 'any' type for the API data since its structure differs from FundProfile
        const apiData: any = response.fund;
        
        // Create a properly formatted FundProfile object
        const formattedFund: FundProfile = {
          id: apiData.fund_id,
          userId: apiData.user_id,
          fundName: apiData.fundName,
          legalStructure: apiData.legalStructure,
          location: apiData.location,
          yearEstablished: apiData.yearEstablished,
          aumRange: apiData.aumRange,
          investmentStrategy: apiData.investmentStrategy,
          profilePurpose: apiData.profilePurpose || [],
          otherPurposeDetails: apiData.otherPurposeDetails,
          teamMembers: (apiData.team_members || []).map((member: any) => ({
            id: member.team_member_id,
            firstName: member.firstName,
            lastName: member.lastName,
            role: member.role,
            yearsExperience: member.yearsExperience,
            education: member.education,
            currentEmployment: member.currentEmployment,
            investmentExpertise: member.investmentExpertise,
            birthDate: member.birthDate,
            linkedin: member.linkedin,
          })),
          activeAt: apiData.active_at
        };
        
        return { 
          success: true, 
          fund: formattedFund 
        };
      } else {
        // Not finding a fund is a legitimate case, not an error
        return { 
          success: response.success,
          error: response.error
        };
      }
    } catch (error: any) {
      this.logger.error('Failed to fetch fund profile', error);
      return { 
        success: false, 
        error: error.message || 'Unknown error'
      };
    }
  }
  
  /**
   * Updates an existing fund profile
   */
  async updateFundProfile(updates: UpdateFundProfileRequest): Promise<{ 
    success: boolean;
    error?: string; 
  }> {
    if (!this.tokenManager.isAuthenticated()) {
      toastService.error('You must be logged in to update your fund profile');
      return { success: false, error: 'Not authenticated' };
    }

    try {
      const response = await this.fundApi.updateFundProfile(updates);
      
      if (response.success) {
        toastService.success('Fund profile updated successfully');
        return { success: true };
      } else {
        toastService.error(response.error || 'Failed to update fund profile');
        return { 
          success: false, 
          error: response.error || 'Unknown error'
        };
      }
    } catch (error: any) {
      this.logger.error('Fund profile update failed', error);
      toastService.error(`Failed to update fund profile: ${error.message}`);
      return { 
        success: false, 
        error: error.message || 'Unknown error'
      };
    }
  }
}