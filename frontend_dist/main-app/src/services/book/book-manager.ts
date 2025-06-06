// frontend_dist/main-app/src/services/book/book-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '@trading-app/auth';
import { BookClient } from '@trading-app/api';
import { Book, BookRequest } from '../../types';
import { toastService } from '../notification/toast-service';

export class BookManager {
  private logger = getLogger('BookManager');
  private bookApi: BookClient;
  private tokenManager: TokenManager;

  constructor(bookApi: BookClient, tokenManager: TokenManager) {
    this.bookApi = bookApi;
    this.tokenManager = tokenManager;
  }

  async createBook(bookData: BookRequest): Promise<{ 
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
    
  // frontend_dist/main-app/src/services/book/book-manager.ts (continued)
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
    
    if (response.success && response.books) {
      const transformedBooks = response.books.map(book => ({
        bookId: book.bookId,
        name: book.name,
        regions: book.regions || [],
        markets: book.markets || [],
        instruments: book.instruments || [],
        investmentApproaches: book.investmentApproaches || [],
        investmentTimeframes: book.investmentTimeframes || [],
        sectors: book.sectors || [],
        positionTypes: book.positionTypes || { long: false, short: false },
        initialCapital: book.initialCapital || 0
      }));
      
      return { success: true, books: transformedBooks };
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

async updateBook(bookId: string, updateData: Partial<BookRequest>): Promise<{ 
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
      toastService.success(`Book updated successfully`);
      
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

async fetchBook(bookId: string): Promise<{ 
  success: boolean; 
  book?: Book;
  error?: string; 
}> {
  if (!this.tokenManager.isAuthenticated()) {
    return { success: false, error: 'Not authenticated' };
  }

  try {
    const response = await this.bookApi.getBook(bookId);
    
    if (response.success && response.book) {
      // Return the book directly - it should match our Book interface
      return { success: true, book: response.book };
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