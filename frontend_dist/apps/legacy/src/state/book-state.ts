import { BehaviorSubject, Observable } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';
import { getLogger } from '../boot/logging';
import { Book } from '@shared/types';

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

export class BookStateService {
  private logger = getLogger('BookStateService');
  private state$ = new BehaviorSubject<BookState>(initialBookState);
  
  // Add this public method to update the entire state
  updateFullState(updates: Partial<BookState>): void {
    const currentState = this.getState();
    this.state$.next({
      ...currentState,
      ...updates,
      lastUpdated: Date.now()
    });
  }

  // Add these methods from other state services
  select<T>(selector: (state: BookState) => T): Observable<T> {
    return this.state$.pipe(
      map(selector),
      distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))
    );
  }

  getState$(): Observable<BookState> {
    return this.state$.asObservable();
  }

  getState(): BookState {
    return this.state$.getValue();
  }

  createBook(book: Book): void {
    const currentState = this.getState();
    this.state$.next({
      ...currentState,
      books: {
        ...currentState.books,
        [book.bookId]: book
      },
      activeBookId: book.bookId,
      lastUpdated: Date.now()
    });
  }

  setActiveBook(bookId: string): void {
    const currentState = this.getState();
    this.state$.next({
      ...currentState,
      activeBookId: bookId,
      lastUpdated: Date.now()
    });
  }

  updateBook(bookId: string, updates: Partial<Book>): void {
    const currentState = this.getState();
    const existingBook = currentState.books[bookId];
    
    if (!existingBook) {
      this.logger.warn(`Attempted to update non-existent book: ${bookId}`);
      return;
    }

    this.state$.next({
      ...currentState,
      books: {
        ...currentState.books,
        [bookId]: {
          ...existingBook,
          ...updates,
        }
      },
      lastUpdated: Date.now()
    });
  }
}

export const bookState = new BookStateService();