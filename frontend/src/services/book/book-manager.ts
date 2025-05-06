// src/services/book/book-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '../auth/token-manager';
import { BookApi } from '../../api/book';
import { Book, CreateBookRequest } from '../../types';
import { bookState } from '../../state/book-state';
import { toastService } from '../notification/toast-service';

interface BookApiResponse {
  id: string;
  user_id: string;
  name: string;
  initialCapital?: number;
  initial_capital?: number;
  riskLevel?: string;
  risk_level?: string;
  marketFocus?: string;
  market_focus?: string;
  tradingStrategy?: string;
  trading_strategy?: string;
  maxPositionSize?: number;
  max_position_size?: number;
  maxTotalRisk?: number;
  max_total_risk?: number;
  status: string;
  createdAt?: number;
  created_at?: number;
  updatedAt?: number;
  updated_at?: number;
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
    
  // In src/services/book/book-manager.ts
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
        // Cast the response to any to bypass TypeScript's type checking
        const apiBooks = response.books as any[];
        
        // Create properly shaped Book objects from the API data
        const formattedBooks = apiBooks.map(apiBook => {
          // Create a book object with the correct shape
          const book: Book = {
            id: apiBook.id,
            userId: apiBook.user_id,
            name: apiBook.name,
            initialCapital: Number(apiBook.initial_capital || 0),
            riskLevel: (apiBook.risk_level || 'medium') as 'low' | 'medium' | 'high',
            status: apiBook.status as 'CONFIGURED' | 'ACTIVE' | 'ARCHIVED',
            createdAt: Number(apiBook.created_at || Date.now()),
            updatedAt: Number(apiBook.updated_at || Date.now())
          };
          
          // Add optional fields if they exist in the API response
          if (apiBook.market_focus) {
            book.marketFocus = apiBook.market_focus;
          }
          
          if (apiBook.trading_strategy) {
            book.tradingStrategy = apiBook.trading_strategy;
          }
          
          if (apiBook.max_position_size) {
            book.maxPositionSize = Number(apiBook.max_position_size);
          }
          
          if (apiBook.max_total_risk) {
            book.maxTotalRisk = Number(apiBook.max_total_risk);
          }
          
          console.log('Formatted book:', book);
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
      
      if (response.success && response.book) {
        // Cast the response to any to handle the snake_case properties
        const apiBook = response.book as any;
        
        // Create a properly formatted Book object from the API response
        const formattedBook: Book = {
          id: apiBook.id,
          userId: apiBook.user_id,
          name: apiBook.name,
          initialCapital: Number(apiBook.initial_capital || 0),
          riskLevel: (apiBook.risk_level || 'medium') as 'low' | 'medium' | 'high',
          status: apiBook.status as 'CONFIGURED' | 'ACTIVE' | 'ARCHIVED',
          createdAt: Number(apiBook.created_at || Date.now()),
          updatedAt: Number(apiBook.updated_at || Date.now())
        };
        
        // Add optional fields if they exist in the API response
        if (apiBook.market_focus) {
          formattedBook.marketFocus = apiBook.market_focus;
        }
        
        if (apiBook.trading_strategy) {
          formattedBook.tradingStrategy = apiBook.trading_strategy;
        }
        
        if (apiBook.max_position_size !== undefined) {
          formattedBook.maxPositionSize = Number(apiBook.max_position_size);
        }
        
        if (apiBook.max_total_risk !== undefined) {
          formattedBook.maxTotalRisk = Number(apiBook.max_total_risk);
        }
        
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