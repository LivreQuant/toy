// src/api/book.ts
import { HttpClient } from './http-client';
import { Book } from '../types'; // Import from types

export interface CreateBookRequest {
  name: string;
  initialCapital: number;
  riskLevel: 'low' | 'medium' | 'high';
  marketFocus?: string;
  tradingStrategy?: string;
  maxPositionSize?: number;
  maxTotalRisk?: number;
}

export class BookApi {
  private client: HttpClient;

  constructor(client: HttpClient) {
    this.client = client;
  }

  async createBook(bookData: CreateBookRequest): Promise<{ 
    success: boolean; 
    bookId?: string; 
    error?: string 
  }> {
    // Change from '/books/create' to '/books'
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
    book?: any; 
    error?: string 
  }> {
    return this.client.get(`/books/${bookId}`);
  }

  async updateBook(bookId: string, updates: Partial<CreateBookRequest>): Promise<{ 
    success: boolean; 
    error?: string 
  }> {
    return this.client.put(`/books/${bookId}`, updates);
  }
}