// src/components/Dashboard/Viewers/ConvictionBlotter/ConvictionFormatInfo.tsx
import React, { useMemo } from 'react';
import { ConvictionModelConfig } from '@trading-app/types-core';
import ConvictionFileProcessor from '../../../../Simulator/ConvictionFileProcessor';
import '../styles/ConvictionFormatInfo.css';

interface ConvictionFormatInfoProps {
  convictionSchema: ConvictionModelConfig | null;
  isLoadingSchema: boolean;
}

const ConvictionFormatInfo: React.FC<ConvictionFormatInfoProps> = ({
  convictionSchema,
  isLoadingSchema
}) => {
  const formatInfo = useMemo(() => {
    if (!convictionSchema) {
      return {
        schemaType: 'Default Schema',
        description: 'Using default conviction format with basic fields',
        sampleFormat: `convictionId,instrumentId,side,score,participationRate,tag
conviction-001,AAPL.US,BUY,5,MEDIUM,value
conviction-002,MSFT.US,SELL,3,LOW,momentum`
      };
    }

    // Use the same logic as in ConvictionFileProcessor
    const processor = new ConvictionFileProcessor(convictionSchema, () => {});
    const { required, optional } = processor.getExpectedColumns();
    const sampleFormat = processor.getSampleFormat();

    let schemaType: string;
    let description: string;

    if (convictionSchema.portfolioApproach === 'target') {
      const method = convictionSchema.targetConvictionMethod;
      schemaType = `Target Portfolio - ${method === 'percent' ? 'Percentage' : 'Notional'}`;
      description = method === 'percent' 
        ? 'Specify target percentage allocation for each instrument'
        : 'Specify target notional amount for each instrument';
    } else {
      const method = convictionSchema.incrementalConvictionMethod;
      switch (method) {
        case 'side_score':
          schemaType = 'Incremental - Side & Score';
          description = `Specify trading side (BUY/SELL/CLOSE) and conviction score (1-${convictionSchema.maxScore || 5})`;
          break;
        case 'side_qty':
          schemaType = 'Incremental - Side & Quantity';
          description = 'Specify trading side (BUY/SELL/CLOSE) and exact quantity';
          break;
        case 'zscore':
          schemaType = 'Incremental - Z-Score';
          description = 'Specify z-score values for position sizing';
          break;
        case 'multi-horizon':
          const horizons = convictionSchema.horizons || [];
          schemaType = 'Incremental - Multi-Horizon Z-Scores';
          description = `Specify z-scores for multiple time horizons: ${horizons.join(', ')}`;
          break;
        default:
          schemaType = 'Incremental - Custom';
          description = 'Custom incremental conviction method';
      }
    }

    return {
      schemaType,
      description,
      sampleFormat,
      requiredFields: required,
      optionalFields: optional
    };
  }, [convictionSchema]);

  if (isLoadingSchema) {
    return (
      <div className="conviction-format-info loading">
        <div className="loading-content">
          <div className="loading-spinner"></div>
          <p>Loading conviction format requirements...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="conviction-format-info">
      <div className="format-header">
        <h3>📋 Expected Conviction File Format</h3>
        <div className="schema-badge">
          {formatInfo.schemaType}
        </div>
      </div>

      <div className="format-description">
        <p>{formatInfo.description}</p>
      </div>

      <div className="format-sections">
        {/* Required Fields Section */}
        <div className="format-section">
          <h4>📌 Required Fields</h4>
          <div className="field-list">
            {formatInfo.requiredFields?.map((field) => (
              <span key={field} className="field-tag required">
                {field}
              </span>
            )) || (
              <span className="field-tag required">convictionId</span>
            )}
          </div>
        </div>

        {/* Optional Fields Section */}
        {formatInfo.optionalFields && formatInfo.optionalFields.length > 0 && (
          <div className="format-section">
            <h4>🔧 Optional Fields</h4>
            <div className="field-list">
              {formatInfo.optionalFields.map((field) => (
                <span key={field} className="field-tag optional">
                  {field}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Sample Format Section */}
        <div className="format-section">
          <h4>📄 Sample CSV Format</h4>
          <div className="sample-format">
            <pre className="format-code">
              {formatInfo.sampleFormat}
            </pre>
          </div>
          <div className="format-notes">
            <p><strong>💡 Tips:</strong></p>
            <ul>
              <li>First row must contain column headers exactly as shown</li>
              <li>Each subsequent row represents one conviction</li>
              <li>Required fields must have values (cannot be empty)</li>
              <li>Optional fields can be left empty or omitted</li>
              {convictionSchema?.portfolioApproach === 'incremental' && 
               convictionSchema?.incrementalConvictionMethod === 'side_score' && (
                <li>Score values must be between 1 and {convictionSchema.maxScore || 5}</li>
              )}
              {convictionSchema?.portfolioApproach === 'target' && 
               convictionSchema?.targetConvictionMethod === 'percent' && (
                <li>Target percentage values should be between -100 and 100</li>
              )}
            </ul>
          </div>
        </div>

        {/* Schema Details Section */}
        {convictionSchema && (
          <div className="format-section schema-details">
            <h4>⚙️ Schema Configuration</h4>
            <div className="schema-info">
              <div className="schema-item">
                <span className="schema-label">Portfolio Approach:</span>
                <span className="schema-value">{convictionSchema.portfolioApproach}</span>
              </div>
              <div className="schema-item">
                <span className="schema-label">Method:</span>
                <span className="schema-value">
                  {convictionSchema.portfolioApproach === 'target' 
                    ? convictionSchema.targetConvictionMethod 
                    : convictionSchema.incrementalConvictionMethod}
                </span>
              </div>
              {convictionSchema.portfolioApproach === 'incremental' && 
               convictionSchema.incrementalConvictionMethod === 'side_score' && (
                <div className="schema-item">
                  <span className="schema-label">Max Score:</span>
                  <span className="schema-value">{convictionSchema.maxScore || 5}</span>
                </div>
              )}
              {convictionSchema.portfolioApproach === 'incremental' && 
               convictionSchema.incrementalConvictionMethod === 'multi-horizon' && 
               convictionSchema.horizons && (
                <div className="schema-item">
                  <span className="schema-label">Horizons:</span>
                  <span className="schema-value">{convictionSchema.horizons.join(', ')}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ConvictionFormatInfo;