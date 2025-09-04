declare module 'papaparse' {
    export interface ParseResult<T> {
      data: T[];
      errors: ParseError[];
      meta: {
        delimiter: string;
        linebreak: string;
        aborted: boolean;
        truncated: boolean;
        cursor: number;
        fields?: string[];
      };
    }
  
    export interface ParseError {
      type: string;
      code: string;
      message: string;
      row: number;
    }
  
    export interface ParseConfig {
      delimiter?: string;
      newline?: string;
      quoteChar?: string;
      escapeChar?: string;
      header?: boolean;
      dynamicTyping?: boolean | { [headerName: string]: boolean };
      preview?: number;
      encoding?: string;
      worker?: boolean;
      comments?: boolean | string;
      download?: boolean;
      skipEmptyLines?: boolean | 'greedy';
      fastMode?: boolean;
      withCredentials?: boolean;
      step?(results: ParseResult<any>, parser: any): void;
      transform?(value: string, field: string | number): any;
      delimitersToGuess?: string[];
      complete?(results: ParseResult<any>, file?: File): void;
      error?(error: ParseError, file?: File): void;
    }
  
    export function parse<T = any>(csv: string | File, config?: ParseConfig): ParseResult<T>;
  
    const Papa: {
      parse<T = any>(csv: string | File, config?: ParseConfig): ParseResult<T>;
    };
  
    export default Papa;
  }