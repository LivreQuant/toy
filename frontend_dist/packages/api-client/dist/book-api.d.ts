import { HttpClient } from './http-client';
import { Book, BookRequest } from '../types';
export declare class BookApi {
    private client;
    constructor(client: HttpClient);
    createBook(bookData: BookRequest): Promise<{
        success: boolean;
        bookId?: string;
        error?: string;
    }>;
    getBooks(): Promise<{
        success: boolean;
        books?: Book[];
        error?: string;
    }>;
    getBook(bookId: string): Promise<{
        success: boolean;
        book?: Book;
        error?: string;
    }>;
    updateBook(bookId: string, updates: Partial<BookRequest>): Promise<{
        success: boolean;
        error?: string;
    }>;
}
