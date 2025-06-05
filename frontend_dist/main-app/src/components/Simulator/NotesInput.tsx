// src/components/Simulator/NotesInput.tsx
import React from 'react';
import './NotesInput.css';

interface NotesInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  maxLength?: number;
}

const NotesInput: React.FC<NotesInputProps> = ({
  value,
  onChange,
  placeholder = "Add notes about this submission...",
  required = false,
  disabled = false,
  maxLength = 1000
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
  };

  return (
    <div className="notes-input-container">
      <div className="notes-header">
        <h4>Notes {required && <span className="required">*</span>}</h4>
        <span className="character-count">
          {value.length}/{maxLength}
        </span>
      </div>
      
      <textarea
        className="notes-input"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={maxLength}
        rows={4}
      />
      
      {required && !value.trim() && (
        <p className="error-message">Notes are required</p>
      )}
    </div>
  );
};

export default NotesInput;