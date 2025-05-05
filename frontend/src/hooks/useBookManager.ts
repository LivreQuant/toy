import { useContext } from 'react';
import { BookManagerContext } from '../contexts/BookContext'; // Corrected import

export const useBookManager = () => {
  const context = useContext(BookManagerContext);
  if (context === null) {
    throw new Error('useBookManager must be used within a BookManagerProvider');
  }
  return context;
};