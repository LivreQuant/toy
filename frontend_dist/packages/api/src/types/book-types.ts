// frontend_dist/packages/api/src/types/book-types.ts
import { Book, BookRequest } from '@trading-app/types-core';

export interface CreateBookResponse {
  success: boolean;
  bookId?: string;
  error?: string;
}

export interface GetBooksResponse {
  success: boolean;
  books?: Book[];
  error?: string;
}

export interface GetBookResponse {
  success: boolean;
  book?: Book;
  error?: string;
}

export interface UpdateBookResponse {
  success: boolean;
  error?: string;
}

export { Book, BookRequest };