// src/pages/BookSetupPage.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useBookManager } from '../../hooks/useBookManager';
//import { useConnection } from '../../hooks/useConnection';
import BaseBookForm from '../Book/BaseBookForm';
import { BookRequest } from '@trading-app/types-core';

const BookSetupPage: React.FC = () => {
  const navigate = useNavigate();
  const bookManager = useBookManager();
  //const { isConnected } = useConnection();

  const handleCreateBook = async (bookData: BookRequest) => {
    //if (!isConnected) {
    //  return { success: false, error: 'Not connected to server' };
    //}
    
    try {
      return await bookManager.createBook(bookData);
    } catch (error: any) {
      console.error('Error creating book:', error);
      return { success: false, error: error.message };
    }
  };

  return (
    <BaseBookForm
      isEditMode={false}
      onSubmit={handleCreateBook}
      submitButtonText="Generate Book"
      title="Portfolio Preferences"
      subtitle="Configure your preferences step by step"
    />
  );
};

export default BookSetupPage;