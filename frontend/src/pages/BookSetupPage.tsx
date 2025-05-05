import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useToast } from '../hooks/useToast';
import { useBookManager } from '../hooks/useBookManager';
import './BookSetupPage.css';

const BookSetupPage: React.FC = () => {
  useRequireAuth();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const bookManager = useBookManager(); // This will now be non-null

  const [formData, setFormData] = useState({
    name: '',
    marketFocus: '',
    riskLevel: 'medium' as 'low' | 'medium' | 'high', // Explicitly type this
    initialCapital: 100000,
    tradingStrategy: '',
    maxPositionSize: undefined,
    maxTotalRisk: undefined
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'initialCapital' 
        ? Number(value) 
        : name === 'riskLevel' 
          ? value as 'low' | 'medium' | 'high' 
          : value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      addToast('warning', 'Please enter a book name');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const result = await bookManager.createBook({
        name: formData.name,
        initialCapital: formData.initialCapital,
        riskLevel: formData.riskLevel, // This is now correctly typed
        marketFocus: formData.marketFocus,
        tradingStrategy: formData.tradingStrategy,
        maxPositionSize: formData.maxPositionSize,
        maxTotalRisk: formData.maxTotalRisk
      });
      
      if (result.success && result.bookId) {
        navigate(`/books/${result.bookId}`);
      }
    } catch (error) {
      addToast('error', 'Failed to create book');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="book-setup-page">
      <h1>Create Trading Book</h1>
      
      <form onSubmit={handleSubmit}>
        {/* Similar form fields as before, with additional strategic inputs */}
        <div className="form-group">
          <label>Risk Level</label>
          <select
            name="riskLevel"
            value={formData.riskLevel}
            onChange={handleChange}
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
        
        {/* Add inputs for market focus, trading strategy, max position size, etc. */}
        
        <button 
          type="submit" 
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Creating Book...' : 'Create Book'}
        </button>
      </form>
    </div>
  );
};

export default BookSetupPage;