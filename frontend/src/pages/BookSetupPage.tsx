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
  const bookManager = useBookManager();

  const [formData, setFormData] = useState({
    name: '',
    initialCapital: 100000,
    riskLevel: 'medium' as 'low' | 'medium' | 'high',
    marketFocus: '',
    tradingStrategy: '',
    maxPositionSize: undefined as number | undefined,
    maxTotalRisk: undefined as number | undefined
  });
  
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    
    // Convert numeric inputs to numbers
    if (type === 'number') {
      setFormData(prev => ({
        ...prev,
        [name]: value ? Number(value) : undefined
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [name]: value
      }));
    }
    
    // Clear error when field is edited
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'Please enter a book name';
    }
    
    if (formData.initialCapital <= 0) {
      newErrors.initialCapital = 'Initial capital must be greater than zero';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const result = await bookManager.createBook({
        name: formData.name,
        initialCapital: formData.initialCapital,
        riskLevel: formData.riskLevel,
        marketFocus: formData.marketFocus || undefined,
        tradingStrategy: formData.tradingStrategy || undefined,
        maxPositionSize: formData.maxPositionSize,
        maxTotalRisk: formData.maxTotalRisk
      });
      
      if (result.success && result.bookId) {
        addToast('success', `Book "${formData.name}" created successfully!`);
        navigate(`/simulator/${result.bookId}`);
      } else {
        addToast('error', result.error || 'Failed to create book');
      }
    } catch (error: any) {
      addToast('error', `Error creating book: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="book-setup-page">
      <h1>Create Trading Book</h1>
      
      <form className="book-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="name">Book Name *</label>
          <input
            id="name"
            name="name"
            type="text"
            value={formData.name}
            onChange={handleChange}
            placeholder="Enter a name for your trading book"
            required
          />
          {errors.name && <div className="error-message">{errors.name}</div>}
        </div>
        
        <div className="form-group">
          <label htmlFor="initialCapital">Initial Capital *</label>
          <input
            id="initialCapital"
            name="initialCapital"
            type="number"
            min="1"
            step="1000"
            value={formData.initialCapital}
            onChange={handleChange}
            required
          />
          {errors.initialCapital && <div className="error-message">{errors.initialCapital}</div>}
        </div>
        
        <div className="form-group">
          <label>Risk Level *</label>
          <div className="risk-selector">
            <label className={formData.riskLevel === 'low' ? 'selected' : ''}>
              <input
                type="radio"
                name="riskLevel"
                value="low"
                checked={formData.riskLevel === 'low'}
                onChange={handleChange}
              />
              Low
            </label>
            <label className={formData.riskLevel === 'medium' ? 'selected' : ''}>
              <input
                type="radio"
                name="riskLevel"
                value="medium"
                checked={formData.riskLevel === 'medium'}
                onChange={handleChange}
              />
              Medium
            </label>
            <label className={formData.riskLevel === 'high' ? 'selected' : ''}>
              <input
                type="radio"
                name="riskLevel"
                value="high"
                checked={formData.riskLevel === 'high'}
                onChange={handleChange}
              />
              High
            </label>
          </div>
        </div>
        
        <div className="form-group">
          <label htmlFor="marketFocus">Market Focus</label>
          <input
            id="marketFocus"
            name="marketFocus"
            type="text"
            value={formData.marketFocus}
            onChange={handleChange}
            placeholder="e.g., Technology, Healthcare, Energy"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="tradingStrategy">Trading Strategy</label>
          <input
            id="tradingStrategy"
            name="tradingStrategy"
            type="text"
            value={formData.tradingStrategy}
            onChange={handleChange}
            placeholder="e.g., Momentum, Value, Trend Following"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="maxPositionSize">Maximum Position Size</label>
          <input
            id="maxPositionSize"
            name="maxPositionSize"
            type="number"
            min="0"
            step="1000"
            value={formData.maxPositionSize || ''}
            onChange={handleChange}
            placeholder="Maximum size for any single position"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="maxTotalRisk">Maximum Total Risk</label>
          <input
            id="maxTotalRisk"
            name="maxTotalRisk"
            type="number"
            min="0"
            step="1000"
            value={formData.maxTotalRisk || ''}
            onChange={handleChange}
            placeholder="Maximum total risk exposure"
          />
        </div>
        
        <div className="form-actions">
          <button
            type="button"
            className="cancel-button"
            onClick={() => navigate('/home')}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="submit-button"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Creating Book...' : 'Create Book'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default BookSetupPage;