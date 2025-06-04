// src/components/Profile/EditFundProfileForm.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { CircularProgress, Box, Typography } from '@mui/material';
import { useFundManager } from '../../hooks/useFundManager';
import { useToast } from '../../hooks/useToast';
import BaseFundProfileForm from './BaseFundProfileForm';
import { FundProfile } from '@shared/types';

const EditFundProfileForm: React.FC = () => {
  const { getFundProfile, updateFundProfile } = useFundManager();
  const { addToast } = useToast();
  const navigate = useNavigate();
  
  const [isLoading, setIsLoading] = useState(true);
  const [fundProfile, setFundProfile] = useState<FundProfile | null>(null);

  // Fetch current fund profile
  useEffect(() => {
    const loadFundProfile = async () => {
      setIsLoading(true);
      
      try {
        const response = await getFundProfile();
        
        if (response.success && response.fund) {
          setFundProfile(response.fund);
        } else {
          // No fund profile found, redirect to create
          addToast('warning', 'No fund profile found. Please create one first.');
          navigate('/profile/create');
        }
      } catch (error: any) {
        addToast('error', `Error loading fund profile: ${error.message}`);
        console.error('Error loading fund profile:', error);
        navigate('/profile/create');
      } finally {
        setIsLoading(false);
      }
    };
    
    loadFundProfile();
  }, [getFundProfile, addToast, navigate]);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Loading fund profile...
        </Typography>
      </Box>
    );
  }

  if (!fundProfile) {
    return null; // This shouldn't happen since we redirect in the useEffect, but just in case
  }

  return (
    <BaseFundProfileForm
      isEditMode={true}
      initialData={fundProfile}
      onSubmit={updateFundProfile}
      submitButtonText="Update Profile"
      title="Edit Fund Profile"
      subtitle="Update your fund's profile for investors and allocators"
    />
  );
};

export default EditFundProfileForm;