// src/book-state.ts
import { BaseStateService } from './base-state-service';
import { Book } from '@trading-app/types-core';

export interface BookState {
  books: Record<string, Book>;
  activeBookId: string | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: number;
}

export const initialBookState: BookState = {
  books: {},
  activeBookId: null,
  isLoading: false,
  error: null,
  lastUpdated: 0
};

export class BookStateService extends BaseStateService<BookState> {
  constructor() {
    super(initialBookState);
  }

  // Override updateState to always update lastUpdated
  updateState(changes: Partial<BookState>): void {
    super.updateState({
      ...changes,
      lastUpdated: Date.now()
    });
  }

  createBook(book: Book): void {
    const currentState = this.getState();
    this.updateState({
      books: {
        ...currentState.books,
        [book.bookId]: book
      },
      activeBookId: book.bookId
    });
  }

  setActiveBook(bookId: string): void {
    this.updateState({
      activeBookId: bookId
    });
  }

  updateBook(bookId: string, updates: Partial<Book>): void {
    const currentState = this.getState();
    const existingBook = currentState.books[bookId];
    
    if (!existingBook) {
      this.logger.warn(`Attempted to update non-existent book: ${bookId}`);
      return;
    }

    this.updateState({
      books: {
        ...currentState.books,
        [bookId]: {
          ...existingBook,
          ...updates,
        }
      }
    });
  }

  reset(): void {
    this.setState(initialBookState);
  }
}

export const bookState = new BookStateService();