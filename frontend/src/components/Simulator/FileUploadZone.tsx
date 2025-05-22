// src/components/Simulator/FileUploadZone.tsx
import React, { useRef, useState, useCallback } from 'react';
import { useToast } from '../../hooks/useToast';
import './FileUploadZone.css';

interface FileUploadZoneProps {
  title: string;
  acceptedTypes: string;
  onFileSelect: (file: File | null) => void;
  file: File | null;
  required?: boolean;
  disabled?: boolean;
  description?: string;
}

const FileUploadZone: React.FC<FileUploadZoneProps> = ({
  title,
  acceptedTypes,
  onFileSelect,
  file,
  required = false,
  disabled = false,
  description
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addToast } = useToast();

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  }, [disabled]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  }, [disabled]);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const validateFile = (file: File): boolean => {
    const acceptedTypesArray = acceptedTypes.split(',').map(type => type.trim());
    
    // Check file type
    const isValidType = acceptedTypesArray.some(type => {
      if (type.startsWith('.')) {
        return file.name.toLowerCase().endsWith(type.toLowerCase());
      }
      return file.type === type;
    });

    if (!isValidType) {
      addToast('error', `Invalid file type. Expected: ${acceptedTypes}`);
      return false;
    }

    // Check file size (10MB limit)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      addToast('error', 'File size must be less than 10MB');
      return false;
    }

    return true;
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (disabled) return;

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && validateFile(droppedFile)) {
      onFileSelect(droppedFile);
      addToast('success', `${title} uploaded: ${droppedFile.name}`);
    }
  }, [disabled, onFileSelect, addToast, title, validateFile]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    const selectedFile = e.target.files[0];
    if (validateFile(selectedFile)) {
      onFileSelect(selectedFile);
      addToast('success', `${title} uploaded: ${selectedFile.name}`);
    }
  }, [onFileSelect, addToast, title, validateFile]);

  const handleBrowseClick = useCallback(() => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, [disabled]);

  const handleRemoveFile = useCallback(() => {
    onFileSelect(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [onFileSelect]);

  return (
    <div className={`file-upload-zone ${disabled ? 'disabled' : ''}`}>
      <div className="file-upload-header">
        <h4>{title} {required && <span className="required">*</span>}</h4>
        {description && <p className="file-description">{description}</p>}
      </div>
      
      <div 
        className={`drop-area ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileInputChange}
          accept={acceptedTypes}
          className="file-input"
          disabled={disabled}
        />
        
        {file ? (
          <div className="file-info">
            <div className="file-details">
              <p className="file-name">{file.name}</p>
              <p className="file-size">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
            <button 
              type="button" 
              onClick={handleRemoveFile}
              className="remove-file-button"
              disabled={disabled}
            >
              ×
            </button>
          </div>
        ) : (
          <div className="drop-message">
            <p>Drop {title.toLowerCase()} here</p>
            <p>or</p>
            <button 
              type="button" 
              onClick={handleBrowseClick}
              className="browse-button"
              disabled={disabled}
            >
              Browse Files
            </button>
            <p className="accepted-types">Accepted: {acceptedTypes}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default FileUploadZone;