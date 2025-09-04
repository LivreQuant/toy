// frontend_dist/book-app/src/components/Dashboard/Container/CustomModal.tsx
import React from 'react';
import './CustomModal.css';

interface CustomModalProps {
  isOpen: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

const CustomModal: React.FC<CustomModalProps> = ({ isOpen, title, onClose, children }) => {
  if (!isOpen) return null;

  return (
    <div className="custom-modal-overlay" onClick={onClose}>
      <div className="custom-modal-container" onClick={(e) => e.stopPropagation()}>
        <div className="custom-modal-header">
          <h3>{title}</h3>
          <button className="custom-modal-close" onClick={onClose}>×</button>
        </div>
        <div className="custom-modal-body">
          {children}
        </div>
      </div>
    </div>
  );
};

export default CustomModal;