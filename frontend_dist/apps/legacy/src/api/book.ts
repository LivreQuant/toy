// frontend/src/api/book.ts

import { HttpClient } from './http-client';
import { Book, BookRequest } from '@shared/types';

export class BookApi {
  private client: HttpClient;

  constructor(client: HttpClient) {
    this.client = client;
  }

  async createBook(bookData: BookRequest): Promise<{ 
    success: boolean; 
    bookId?: string; 
    error?: string 
  }> {
    return this.client.post('/books', bookData);
  }

  async getBooks(): Promise<{ 
    success: boolean; 
    books?: Book[]; 
    error?: string 
  }> {
    return this.client.get('/books');
  }

  async getBook(bookId: string): Promise<{ 
    success: boolean; 
    book?: Book; 
    error?: string 
  }> {
    return this.client.get(`/books/${bookId}`);
  }

  async updateBook(bookId: string, updates: Partial<BookRequest>): Promise<{ 
    success: boolean; 
    error?: string 
  }> {
    return this.client.put(`/books/${bookId}`, updates);
  }
}