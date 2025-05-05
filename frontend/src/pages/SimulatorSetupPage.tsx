// src/pages/SimulationSetupPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useToast } from '../hooks/useToast';
import './SimulationSetupPage.css';

const SimulationSetupPage: React.FC = () => {
  useRequireAuth();
  const navigate = useNavigate();
  const { addToast } = useToast();
  
  const [formData, setFormData] = useState({
    name: '',
    sector: '',
    riskLevel: 'medium',
    initialCapital: 100000
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'initialCapital' ? Number(value) : value
    }));
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      addToast('warning', 'Please enter a simulation name');
      return;
    }
    
    if (!formData.sector.trim()) {
      addToast('warning', 'Please select a sector');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // In a real implementation, this would call an API to create the simulation
      // For now, we'll just simulate a successful creation
      
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Mock successful creation
      const newSimulationId = Date.now().toString();
      
      addToast('success', 'Simulation created successfully!');
      
      // Navigate back to home page
      navigate('/home');
    } catch (error) {
      addToast('error', `Failed to create simulation: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const handleCancel = () => {
    navigate('/home');
  };
  
  return (
    <div className="simulation-setup-page">
      <h1>Initialize Trading Simulation</h1>
      
      <form className="simulation-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="name">Simulation Name</label>
          <input
            id="name"
            name="name"
            type="text"
            value={formData.name}
            onChange={handleChange}
            placeholder="E.g., Tech Sector Portfolio"
            disabled={isSubmitting}
            required
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="sector">Market Sector</label>
          <select
            id="sector"
            name="sector"
            value={formData.sector}
            onChange={handleChange}
            disabled={isSubmitting}
            required
          >
            <option value="">Select a sector</option>
            <option value="Technology">Technology</option>
            <option value="Healthcare">Healthcare</option>
            <option value="Financial">Financial</option>
            <option value="Consumer">Consumer</option>
            <option value="Energy">Energy</option>
            <option value="Mixed">Mixed - Multiple Sectors</option>
          </select>
        </div>
        
        <div className="form-group">
          <label htmlFor="riskLevel">Risk Level</label>
          <div className="risk-selector">
            <label className={formData.riskLevel === 'low' ? 'selected' : ''}>
              <input
                type="radio"
                name="riskLevel"
                value="low"
                checked={formData.riskLevel === 'low'}
                onChange={handleChange}
                disabled={isSubmitting}
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
                disabled={isSubmitting}
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
                disabled={isSubmitting}
              />
              High
            </label>
          </div>
        </div>
        
        <div className="form-group">
          <label htmlFor="initialCapital">Initial Capital ($)</label>
          <input
            id="initialCapital"
            name="initialCapital"
            type="number"
            min="10000"
            step="10000"
            value={formData.initialCapital}
            onChange={handleChange}
            disabled={isSubmitting}
            required
          />
        </div>
        
        <div className="form-actions">
          <button
            type="button"
            onClick={handleCancel}
            className="cancel-button"
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="submit-button"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Creating...' : 'Create Simulation'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default SimulationSetupPage;