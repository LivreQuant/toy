// frontend_dist/main-app/src/contexts/BookContext.tsx
import React, { createContext, ReactNode } from 'react';
import { BookManager } from '../services/book/book-manager';
import { BookClient } from '@trading-app/api';
import { Book, BookRequest } from '../types';
import { TokenManager } from '@trading-app/auth';

interface BookManagerContextType {
  createBook: (bookData: BookRequest) => Promise<{ success: boolean; bookId?: string; error?: string }>;
  fetchBooks: () => Promise<{ success: boolean; books?: Book[]; error?: string }>;
  fetchBook: (bookId: string) => Promise<{ success: boolean; book?: Book; error?: string }>;
  updateBook: (bookId: string, updateData: Partial<BookRequest>) => Promise<{ success: boolean; error?: string }>;
}

export const BookManagerContext = createContext<BookManagerContextType | null>(null);

export const BookManagerProvider: React.FC<{ 
  children: ReactNode; 
  bookClient: BookClient; 
  tokenManager: TokenManager;
}> = ({ children, bookClient, tokenManager }) => {
  const bookManager = new BookManager(bookClient, tokenManager);

  const contextValue: BookManagerContextType = {
    createBook: bookManager.createBook.bind(bookManager),
    fetchBooks: bookManager.fetchBooks.bind(bookManager),
    fetchBook: bookManager.fetchBook.bind(bookManager),
    updateBook: bookManager.updateBook.bind(bookManager)
  };

  return (
    <BookManagerContext.Provider value={contextValue}>
      {children}
    </BookManagerContext.Provider>
  );
};