// src/pages/EditBookPage.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useToast } from '../../hooks/useToast';
import { useBookManager } from '../../hooks/useBookManager';
import { useConnection } from '../../hooks/useConnection';
import BaseBookForm from '../Book/BaseBookForm';
import { BookRequest } from '@shared/types';

// Add this interface to extend BookRequest with bookId
interface ExtendedBookRequest extends BookRequest {
  bookId?: string;
}

const EditBookPage: React.FC = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { isConnected } = useConnection();
  const { addToast } = useToast();
  const bookManager = useBookManager();
  
  const [isLoading, setIsLoading] = useState(true);
  const [bookData, setBookData] = useState<Partial<BookRequest>>({});

  useEffect(() => {
    const fetchBookDetails = async () => {
      if (!bookId || !isConnected) return;
      
      setIsLoading(true);
      
      try {
        const response = await bookManager.fetchBook(bookId);
        
        if (response.success && response.book) {
          setBookData(response.book);
        } else {
          addToast('error', response.error || 'Failed to fetch book details');
          navigate('/home');
        }
      } catch (error: any) {
        console.error('Error fetching book details:', error);
        addToast('error', `Failed to load book details: ${error.message}`);
        navigate('/home');
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchBookDetails();
  }, [bookId, isConnected, bookManager, addToast, navigate]);

  const handleUpdateBook = async (formData: BookRequest) => {
    if (!bookId) {
      return { success: false, error: 'No book ID found' };
    }
    
    try {
      return await bookManager.updateBook(bookId, formData);
    } catch (error: any) {
      console.error('Error updating book:', error);
      return { success: false, error: error.message };
    }
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px' }}>
        <CircularProgress />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Loading book details...
        </Typography>
      </Box>
    );
  }

  // Create an extended version of bookData that includes the bookId
  const extendedBookData: Partial<ExtendedBookRequest> = {
    ...bookData,
    bookId
  };

  return (
    <BaseBookForm
      isEditMode={true}
      initialData={extendedBookData}
      onSubmit={handleUpdateBook}
      submitButtonText="Update Book"
      title="Edit Book"
      subtitle="Update your book's preferences step by step"
    />
  );
};

export default EditBookPage;