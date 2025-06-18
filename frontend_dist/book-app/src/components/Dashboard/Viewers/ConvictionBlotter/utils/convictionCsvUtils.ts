// src/components/Dashboard/Viewers/ConvictionBlotter/utils/convictionCsvUtils.ts
import Papa from 'papaparse';
import { processConvictionCsvData } from './convictionValidation';

// Expected CSV headers for conviction files (will be dynamic based on schema)
const BASE_HEADERS = ['convictionId', 'instrumentId'];

// Function to validate the CSV file structure
export const validateConvictionsCsv = (file: File): Promise<boolean> => {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      preview: 1,
      skipEmptyLines: true,
      complete: (results) => {
        const headers = results.meta.fields || [];
        const missingHeaders = BASE_HEADERS.filter(header => !headers.includes(header));
        
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

// Function to parse the CSV file and convert it to conviction objects
export const parseConvictionsCsv = (file: File): Promise<{ convictions: any[]; hasErrors: boolean }> => {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true,
      complete: (results) => {
        try {
          const processed = processConvictionCsvData(results);
          // Convert from the function's return format to match expected format
          resolve({
            convictions: processed.convictions,
            hasErrors: processed.hasErrors
          });
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