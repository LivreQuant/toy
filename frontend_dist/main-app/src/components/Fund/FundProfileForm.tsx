// src/components/Profile/FundProfileForm.tsx
import React from 'react';
import { useFundManager } from '../../hooks/useFundManager';
import BaseFundProfileForm from './BaseFundProfileForm2';

const FundProfileForm: React.FC = () => {
  const { createFundProfile } = useFundManager();

  return (
    <BaseFundProfileForm
      isEditMode={false}
      onSubmit={createFundProfile}
      submitButtonText="Submit Profile"
      title="Fund Profile"
      subtitle="Create your fund's profile for investors and allocators"
    />
  );
};

export default FundProfileForm;