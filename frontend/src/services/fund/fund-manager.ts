// src/services/fund/fund-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '../auth/token-manager';
import { FundApi } from '../../api/fund';
import { FundProfile, CreateFundProfileRequest, UpdateFundProfileRequest } from '../../types';
import { toastService } from '../notification/toast-service';

export class FundManager {
  private logger = getLogger('FundManager');
  private fundApi: FundApi;
  private tokenManager: TokenManager;

  constructor(fundApi: FundApi, tokenManager: TokenManager) {
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
  // Updated useFundManager hook implementation (partial) to handle the API response format
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
        // Transform the API response structure to match our FundProfile type
        const apiData = response.fund;
        
        // Extract profile data from the nested structure
        const profileData = apiData.properties?.general?.profile || {};
        
        // Map team members from the API format to our format
        const teamMembers = apiData.team_members?.map(member => {
          const personal = member.properties?.personal?.info || {};
          const professional = member.properties?.professional?.info || {};
          const education = member.properties?.education?.info || {};
          
          return {
            id: member.team_member_id,
            firstName: personal.firstName || '',
            lastName: personal.lastName || '',
            role: professional.role || '',
            yearsExperience: professional.yearsExperience || '',
            education: education.institution || '',
            currentEmployment: professional.currentEmployment || '',
            investmentExpertise: professional.investmentExpertise || '',
            birthDate: personal.birthDate || '',
            linkedin: professional.linkedin || '',
          };
        }) || [];
        
        // Create a properly formatted FundProfile
        const formattedFund: FundProfile = {
          id: apiData.fund_id,
          userId: apiData.user_id,
          fundName: apiData.name,
          legalStructure: profileData.legalStructure,
          location: profileData.location,
          yearEstablished: profileData.yearEstablished,
          aumRange: profileData.aumRange,
          investmentStrategy: apiData.properties?.general?.strategy?.thesis || '',
          profilePurpose: profileData.purpose || [],
          otherPurposeDetails: profileData.otherDetails,
          teamMembers: teamMembers,
          createdAt: apiData.created_at,
          updatedAt: apiData.updated_at
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