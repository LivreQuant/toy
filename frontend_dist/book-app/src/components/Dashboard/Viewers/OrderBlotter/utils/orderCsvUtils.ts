// src/components/Dashboard/Viewers/OrderBlotter/orderCsvUtils.ts
import Papa from 'papaparse';
import { processOrderCsvData } from './orderValidation';

// Expected CSV headers for order files
const EXPECTED_HEADERS = [
  'orderSide', 'instrument', 'exchange', 'quantity', 'currency', 'price', 'orderType', 'fillRate', 'clOrderId'
];

// Function to validate the CSV file structure
export const validateOrdersCsv = (file: File): Promise<boolean> => {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      preview: 1, // Only check the headers and first row
      skipEmptyLines: true,
      complete: (results) => {
        // Check if all expected headers are present
        const headers = results.meta.fields || [];
        const missingHeaders = EXPECTED_HEADERS.filter(header => !headers.includes(header));
        
        if (missingHeaders.length > 0) {
          reject(new Error(`Missing required headers: ${missingHeaders.join(', ')}`));
          return;
        }
        
        resolve(true);
      },
      error: (error) => {
        reject(error);
      }
    });
  });
};

// Function to parse the CSV file and convert it to order objects
export const parseOrdersCsv = (file: File): Promise<{ orders: any[]; hasErrors: boolean }> => {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true, // Automatically convert numeric values
      complete: (results) => {
        try {
          // Process and validate the CSV data
          const processed = processOrderCsvData(results);
          resolve(processed);
        } catch (error) {
          reject(error);
        }
      },
      error: (error) => {
        reject(error);
      }
    });
  });
};