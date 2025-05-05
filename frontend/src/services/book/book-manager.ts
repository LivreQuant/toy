// src/services/book/book-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '../auth/token-manager';
import { BookApi } from '../../api/book';
import { Book, CreateBookRequest } from '../../types';
import { bookState } from '../../state/book-state';
import { toastService } from '../notification/toast-service';

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
      
      if (response.success && response.books) {
        // Update book state if state management is being used
        if (bookState) {
          const booksMap = response.books.reduce((acc, book) => {
            acc[book.id] = book;
            return acc;
          }, {} as Record<string, Book>);
          
          bookState.updateFullState({
            books: booksMap,
            isLoading: false,
            error: null,
            lastUpdated: Date.now()
          });
        }
        
        return { 
          success: true, 
          books: response.books 
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
}