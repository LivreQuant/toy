import React, { createContext, ReactNode } from 'react';
import { BookManager } from '../services/book/book-manager';
import { BookApi } from '../api/book'; // Import BookApi explicitly
import { Book } from '../types';
import { httpClient, tokenManager } from '../api/api-client'; // Ensure these are exported

interface BookManagerContextType {
  createBook: (bookData: { 
    name: string;
    details: Array<[string, string, string]>; 
  }) => Promise<{ success: boolean; bookId?: string; error?: string }>;
  fetchBooks: () => Promise<{ success: boolean; books?: Book[]; error?: string }>;
  fetchBook: (bookId: string) => Promise<{ success: boolean; book?: Book; error?: string }>;
}

export const BookManagerContext = createContext<BookManagerContextType | null>(null);

export const BookManagerProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const bookApi = new BookApi(httpClient);
  const bookManager = new BookManager(bookApi, tokenManager);

  const contextValue: BookManagerContextType = {
    createBook: bookManager.createBook.bind(bookManager),
    fetchBooks: bookManager.fetchBooks.bind(bookManager),
    fetchBook: bookManager.fetchBook.bind(bookManager)
  };

  return (
    <BookManagerContext.Provider value={contextValue}>
      {children}
    </BookManagerContext.Provider>
  );
};