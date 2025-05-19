// src/services/fund/fund-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '../auth/token-manager';
import { FundApi } from '../../api/fund';
import { FundProfile, TeamMember, CreateFundProfileRequest, UpdateFundProfileRequest } from '../../types';
import { toastService } from '../notification/toast-service';


// Add this interface to define the structure of the API response
interface FundProfileApiResponse {
  fund_id: string;
  user_id: string;
  name: string;
  status: string;
  active_at: number;
  expire_at: number;
  properties?: {
    general?: {
      profile?: {
        legalStructure?: string;
        location?: string;
        yearEstablished?: string;
        aumRange?: string;
        purpose?: string[];
        otherDetails?: string;
      };
      strategy?: {
        thesis?: string;
      };
    };
  };
  team_members?: Array<{
    team_member_id: string;
    properties?: {
      personal?: {
        info?: {
          firstName?: string;
          lastName?: string;
          birthDate?: string;
        };
      };
      professional?: {
        info?: {
          role?: string;
          yearsExperience?: string;
          currentEmployment?: string;
          investmentExpertise?: string;
          linkedin?: string;
        };
      };
      education?: {
        info?: {
          institution?: string;
        };
      };
    };
  }>;
}


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
        // Cast the response.fund to any to handle different structures
        const apiData = response.fund as any;
        
        // Create a properly formatted FundProfile
        const formattedFund: FundProfile = {
          id: apiData.fund_id || apiData.id,
          userId: apiData.user_id || apiData.userId,
          fundName: apiData.name,
          
          // Check both flat and nested structures
          legalStructure: apiData.legalStructure || 
            apiData.fund_type_legal_structure,
            
          location: apiData.location || 
            apiData.location_address,
            
          yearEstablished: apiData.yearEstablished || 
            apiData.metadata_year_established,
            
          aumRange: apiData.aumRange || 
            apiData.financial_aum_range,
            
          investmentStrategy: apiData.investmentStrategy || 
            apiData.strategy_approach,
            
          profilePurpose: apiData.profilePurpose || 
            apiData.purpose_objective || [],
            
          otherPurposeDetails: apiData.otherPurposeDetails || 
            apiData.purpose_description,
            
          // Process team members with careful extraction of nested fields
          teamMembers: apiData.team_members?.map((member: any) => {
            // Handle different team member structures
            return {
              id: member.team_member_id || member.id,
              firstName: member.personal?.firstName || '',
              lastName: member.personal?.lastName || '',
              role: member.professional?.role || '',
              yearsExperience: member.professional?.yearsExperience || '',
              // Specifically handle education as a string value
              education: typeof member.education === 'object' && member.education?.institution 
                ? member.education.institution 
                : (typeof member.education === 'string' ? member.education : ''),
              currentEmployment: member.professional?.currentEmployment || '',
              investmentExpertise: member.professional?.investmentExpertise || '',
              birthDate: member.personal?.birthDate || '',
              linkedin: member.professional?.linkedin || '',
            };
          }) || [],
          
          activeAt: apiData.active_at || apiData.activeAt,
          expireAt: apiData.expire_at || apiData.expireAt
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