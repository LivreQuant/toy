import { BaseStateService } from './base-state-service';
import { Book } from '@trading-app/types-core';
export interface BookState {
    books: Record<string, Book>;
    activeBookId: string | null;
    isLoading: boolean;
    error: string | null;
    lastUpdated: number;
}
export declare const initialBookState: BookState;
export declare class BookStateService extends BaseStateService<BookState> {
    constructor();
    updateState(changes: Partial<BookState>): void;
    createBook(book: Book): void;
    setActiveBook(bookId: string): void;
    updateBook(bookId: string, updates: Partial<Book>): void;
    reset(): void;
}
export declare const bookState: BookStateService;
