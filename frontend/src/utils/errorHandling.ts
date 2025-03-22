// src/utils/errorHandling.ts

/**
 * Extracts error message from various API response formats
 */
export function extractErrorMessage(error: any): string {
    if (!error) return 'Unknown error';
    
    // Handle different error formats
    if (typeof error === 'string') return error;
    
    if (error instanceof Error) return error.message;
    
    // API response formats
    if (error.error_message) return error.error_message;
    if (error.errorMessage) return error.errorMessage;
    if (error.error) return typeof error.error === 'string' ? error.error : 'Unknown error';
    if (error.message) return error.message;
    
    return 'Unknown error occurred';
  }
  
  /**
   * Standardizes error handling for API fetch calls
   */
  export async function handleApiResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let errorMessage: string;
      
      try {
        const errorData = await response.json();
        errorMessage = extractErrorMessage(errorData) || `Request failed with status ${response.status}`;
      } catch (e) {
        errorMessage = `Request failed with status ${response.status}`;
      }
      
      throw new Error(errorMessage);
    }
    
    return await response.json() as T;
  }