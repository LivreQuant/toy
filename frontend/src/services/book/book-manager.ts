
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
    bookId?: string 
  }> {
    if (!this.tokenManager.isAuthenticated()) {
      toastService.error('You must be logged in to create a book');
      return { success: false };
    }

    try {
      const response = await this.bookApi.createBook(bookData);
      
      if (response.success && response.bookId) {
        toastService.success(`Book "${bookData.name}" created successfully`);
        
        await this.fetchBooks();
        
        return { 
          success: true, 
          bookId: response.bookId 
        };
      } else {
        toastService.error(response.error || 'Failed to create book');
        return { success: false };
      }
    } catch (error: any) {
      this.logger.error('Book creation failed', error);
      toastService.error(`Failed to create book: ${error.message}`);
      return { success: false };
    }
  }

  async fetchBooks(): Promise<void> {
    if (!this.tokenManager.isAuthenticated()) {
      return;
    }

    try {
      const response = await this.bookApi.getBooks();
      
      if (response.success && response.books) {
        const booksMap = response.books.reduce((acc, book) => {
          acc[book.id] = book;
          return acc;
        }, {} as Record<string, Book>);

        // Use the new updateFullState method
        bookState.updateFullState({
          books: booksMap,
          activeBookId: null,
          isLoading: false,
          error: null
        });
      } else {
        toastService.error(response.error || 'Failed to fetch books');
      }
    } catch (error: any) {
      this.logger.error('Failed to fetch books', error);
      toastService.error(`Failed to fetch books: ${error.message}`);
    }
  }
}