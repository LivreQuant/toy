// src/services/book/book-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '../auth/token-manager';
import { BookApi } from '../../api/book';
import { Book, CreateBookRequest } from '../../types';
import { bookState } from '../../state/book-state';
import { toastService } from '../notification/toast-service';

interface BookApiResponse {
  book_id: string;
  id?: string; 
  user_id: string;
  userId?: string;
  name: string;
  status: string;
  active_at: number;
  activeAt?: number;
  expire_at: number;
  expireAt?: number;
  parameters: any;
}


// Define a type guard to check if a status string is valid for our Book type
function isValidBookStatus(status: string): status is 'CONFIGURED' | 'ACTIVE' | 'ARCHIVED' {
  return ['CONFIGURED', 'ACTIVE', 'ARCHIVED'].includes(status);
}

export class BookManager {
  private logger = getLogger('BookManager');
  private bookApi: BookApi;
  private tokenManager: TokenManager;

  constructor(bookApi: BookApi, tokenManager: TokenManager) {
    this.bookApi = bookApi;
    this.tokenManager = tokenManager;
  }

  async createBook(bookData: CreateBookRequest): Promise<{ 
    success: boolean; 
    bookId?: string;
    error?: string; 
  }> {
    if (!this.tokenManager.isAuthenticated()) {
      toastService.error('You must be logged in to create a book');
      return { success: false, error: 'Not authenticated' };
    }

    try {
      const response = await this.bookApi.createBook(bookData);
      
      if (response.success && response.bookId) {
        toastService.success(`Book "${bookData.name}" created successfully`);
        
        // Refresh books after creation
        await this.fetchBooks();
        
        return { 
          success: true, 
          bookId: response.bookId 
        };
      } else {
        toastService.error(response.error || 'Failed to create book');
        return { 
          success: false, 
          error: response.error || 'Unknown error'
        };
      }
    } catch (error: any) {
      this.logger.error('Book creation failed', error);
      toastService.error(`Failed to create book: ${error.message}`);
      return { 
        success: false, 
        error: error.message || 'Unknown error'
      };
    }
  }
    
  async fetchBooks(): Promise<{ 
    success: boolean; 
    books?: Book[];
    error?: string; 
  }> {
    if (!this.tokenManager.isAuthenticated()) {
      return { success: false, error: 'Not authenticated' };
    }
  
    try {
      const response = await this.bookApi.getBooks();
      console.log('Raw API response:', response);
      
      if (response.success && response.books) {
        // Process the books array from the API response
        // Use 'any' as the type for apiBook temporarily
        const formattedBooks = response.books.map((apiBook: any) => {
          // Create a properly shaped Book object from the API data
          const book: Book = {
            id: apiBook.book_id || apiBook.id, // Handle both formats
            userId: apiBook.user_id || apiBook.userId,
            name: apiBook.name,
            initialCapital: 0, // Will be updated from parameters
            riskLevel: 'medium', // Default value
            status: apiBook.status,
            activeAt: apiBook.active_at || apiBook.activeAt,
            expireAt: apiBook.expire_at || apiBook.expireAt
          };
          
          // Extract initialCapital from parameters if available
          if (apiBook.parameters) {
            const params = Array.isArray(apiBook.parameters) ? apiBook.parameters : JSON.parse(apiBook.parameters);
            
            // Find allocation parameter
            const allocationParam = params.find((p: any) => 
              Array.isArray(p) && p[0] === 'Allocation'
            );
            
            if (allocationParam && allocationParam[2]) {
              book.initialCapital = parseFloat(allocationParam[2]);
            }
            
            // Find market focus parameter
            const marketParam = params.find((p: any) => 
              Array.isArray(p) && p[0] === 'Market'
            );
            
            if (marketParam && marketParam[2]) {
              book.marketFocus = marketParam[2];
            }
            
            // Find investment approach parameter (trading strategy)
            const approachParams = params.filter((p: any) => 
              Array.isArray(p) && p[0] === 'Investment Approach'
            );
            
            if (approachParams.length > 0) {
              book.tradingStrategy = approachParams.map((p: any) => p[2]).join(', ');
            }
            
            // Find region parameter
            const regionParam = params.find((p: any) => 
              Array.isArray(p) && p[0] === 'Region'
            );
            
            if (regionParam && regionParam[2]) {
              book.region = regionParam[2];
            }
            
            // Find instrument parameter
            const instrumentParam = params.find((p: any) => 
              Array.isArray(p) && p[0] === 'Instrument'
            );
            
            if (instrumentParam && instrumentParam[2]) {
              book.instrument = instrumentParam[2];
            }
          }
          
          return book;
        });
        
        return { 
          success: true, 
          books: formattedBooks 
        };
      } else {
        return { 
          success: false, 
          error: response.error || 'Failed to fetch books'
        };
      }
    } catch (error: any) {
      this.logger.error('Failed to fetch books', error);
      return { 
        success: false, 
        error: error.message || 'Unknown error'
      };
    }
  }

  async updateBook(bookId: string, updateData: {
    name: string;
    parameters: Array<[string, string, string]>;
  }): Promise<{ 
    success: boolean; 
    error?: string 
  }> {
    if (!this.tokenManager.isAuthenticated()) {
      toastService.error('You must be logged in to update a book');
      return { success: false, error: 'Not authenticated' };
    }

    try {
      const response = await this.bookApi.updateBook(bookId, updateData);
      
      if (response.success) {
        toastService.success(`Book "${updateData.name}" updated successfully`);
        
        // Refresh books after update
        await this.fetchBooks();
        
        return { success: true };
      } else {
        toastService.error(response.error || 'Failed to update book');
        return { 
          success: false, 
          error: response.error || 'Unknown error'
        };
      }
    } catch (error: any) {
      this.logger.error('Book update failed', error);
      toastService.error(`Failed to update book: ${error.message}`);
      return { 
        success: false, 
        error: error.message || 'Unknown error'
      };
    }
  }

  // In src/services/book/book-manager.ts
  async fetchBook(bookId: string): Promise<{ 
    success: boolean; 
    book?: Book;
    error?: string; 
  }> {
    if (!this.tokenManager.isAuthenticated()) {
      return { success: false, error: 'Not authenticated' };
    }
  
    try {
      // Implement getBook in BookApi if it doesn't exist
      const response = await this.bookApi.getBook(bookId);
      console.log('Raw book data from API:', response.book);
      
      if (response.success && response.book) {
        // Cast the response to any to handle the snake_case properties
        const apiBook = response.book as any;
        
        // Create a properly formatted Book object from the API response
        const formattedBook: Book = {
          id: apiBook.book_id || apiBook.id, // Handle both formats
          userId: apiBook.user_id || apiBook.userId,
          name: apiBook.name,
          initialCapital: 0, // Default value, will update from parameters
          riskLevel: 'medium', // Default value
          status: apiBook.status,
          activeAt: apiBook.active_at || apiBook.activeAt || Date.now(),
          expireAt: apiBook.expire_at || apiBook.expireAt || Date.now(),
          parameters: apiBook.parameters // Include parameters from API response
        };
        
        // Extract initialCapital from parameters if available
        if (apiBook.parameters) {
          const params = Array.isArray(apiBook.parameters) ? apiBook.parameters : JSON.parse(apiBook.parameters);
          
          // Find allocation parameter
          const allocationParam = params.find((p: any) => 
            Array.isArray(p) && p[0] === 'Allocation'
          );
          
          if (allocationParam && allocationParam[2]) {
            formattedBook.initialCapital = parseFloat(allocationParam[2]);
          }
          
          // Find market focus parameter
          const marketParam = params.find((p: any) => 
            Array.isArray(p) && p[0] === 'Market'
          );
          
          if (marketParam && marketParam[2]) {
            formattedBook.marketFocus = marketParam[2];
          }
          
          // Find investment approach parameter (trading strategy)
          const approachParams = params.filter((p: any) => 
            Array.isArray(p) && p[0] === 'Investment Approach'
          );
          
          if (approachParams.length > 0) {
            formattedBook.tradingStrategy = approachParams.map((p: any) => p[2]).join(', ');
          }
          
          // Find region parameter
          const regionParam = params.find((p: any) => 
            Array.isArray(p) && p[0] === 'Region'
          );
          
          if (regionParam && regionParam[2]) {
            formattedBook.region = regionParam[2];
          }
          
          // Find instrument parameter
          const instrumentParam = params.find((p: any) => 
            Array.isArray(p) && p[0] === 'Instrument'
          );
          
          if (instrumentParam && instrumentParam[2]) {
            formattedBook.instrument = instrumentParam[2];
          }
        }
        
        console.log('Formatted book:', formattedBook);
        return { 
          success: true, 
          book: formattedBook 
        };
      } else {
        return { 
          success: false, 
          error: response.error || 'Failed to fetch book details'
        };
      }
    } catch (error: any) {
      this.logger.error('Failed to fetch book details', error);
      return { 
        success: false, 
        error: error.message || 'Unknown error'
      };
    }
  }
}