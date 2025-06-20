// frontend_dist/packages/api/src/clients/book-client.ts
import { BaseApiClient } from '../core/base-client';
import {
  BookRequest,
  CreateBookResponse,
  GetBooksResponse,
  GetBookResponse,
  UpdateBookResponse,
  ClientConfigResponse,
  ClientConfigUpdateRequest,
  ClientConfigUpdateResponse
} from '../types/book-types';

export class BookClient extends BaseApiClient {
  async createBook(bookData: BookRequest): Promise<CreateBookResponse> {
    return this.post('/books', bookData);
  }

  async getBooks(): Promise<GetBooksResponse> {
    return this.get('/books');
  }

  async getBook(bookId: string): Promise<GetBookResponse> {
    return this.get(`/books/${bookId}`);
  }

  async updateBook(bookId: string, updates: Partial<BookRequest>): Promise<UpdateBookResponse> {
    return this.put(`/books/${bookId}`, updates);
  }

  async getClientConfig(bookId: string): Promise<ClientConfigResponse> {
    return this.get(`/books/${bookId}/config`);
  }

  async updateClientConfig(bookId: string, config: string): Promise<ClientConfigUpdateResponse> {
    return this.put(`/books/${bookId}/config`, { config });
  }
}