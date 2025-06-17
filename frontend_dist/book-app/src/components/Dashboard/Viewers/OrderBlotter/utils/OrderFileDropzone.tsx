// src/components/Viewers/OrderBlotter/OrderFileDropzone.tsx
import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Icon } from '@blueprintjs/core';

// Make sure to install react-dropzone first
// npm install react-dropzone

interface OrderFileDropzoneProps {
  onFileAccepted: (file: File) => void;
}

const OrderFileDropzone: React.FC<OrderFileDropzoneProps> = ({ onFileAccepted }) => {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      onFileAccepted(acceptedFiles[0]);
    }
  }, [onFileAccepted]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.csv']
    },
    maxFiles: 1
  });

  return (
    <div 
      {...getRootProps()} 
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px',
        border: '2px dashed #5C7080',
        borderRadius: '5px',
        background: isDragActive ? '#394B59' : '#30404D',
        color: '#F5F8FA',
        outline: 'none',
        transition: 'border .24s ease-in-out',
        margin: '20px',
        flex: 1,
        cursor: 'pointer'
      }}
    >
      <input {...getInputProps()} />
      <Icon icon="cloud-upload" size={50} style={{ marginBottom: '20px' }} />
      <h3 style={{ textAlign: 'center', marginBottom: '10px' }}>
        {isDragActive ? 'Drop the CSV file here' : 'Drag & drop a CSV file here, or click to select'}
      </h3>
      <p style={{ textAlign: 'center', color: '#A7B6C2' }}>
        Only CSV files with valid order data will be accepted
      </p>
    </div>
  );
};

export default OrderFileDropzone;