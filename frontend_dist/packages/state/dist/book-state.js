// src/book-state.ts
import { BaseStateService } from './base-state-service';
export const initialBookState = {
    books: {},
    activeBookId: null,
    isLoading: false,
    error: null,
    lastUpdated: 0
};
export class BookStateService extends BaseStateService {
    constructor() {
        super(initialBookState);
    }
    // Override updateState to always update lastUpdated
    updateState(changes) {
        super.updateState(Object.assign(Object.assign({}, changes), { lastUpdated: Date.now() }));
    }
    createBook(book) {
        const currentState = this.getState();
        this.updateState({
            books: Object.assign(Object.assign({}, currentState.books), { [book.bookId]: book }),
            activeBookId: book.bookId
        });
    }
    setActiveBook(bookId) {
        this.updateState({
            activeBookId: bookId
        });
    }
    updateBook(bookId, updates) {
        const currentState = this.getState();
        const existingBook = currentState.books[bookId];
        if (!existingBook) {
            this.logger.warn(`Attempted to update non-existent book: ${bookId}`);
            return;
        }
        this.updateState({
            books: Object.assign(Object.assign({}, currentState.books), { [bookId]: Object.assign(Object.assign({}, existingBook), updates) })
        });
    }
    reset() {
        this.setState(initialBookState);
    }
}
export const bookState = new BookStateService();
