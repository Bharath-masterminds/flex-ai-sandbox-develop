import pandas as pd
import json
import logging
import streamlit as st
from io import StringIO
from typing import Optional

class FileHandler:
    """
    Handle file uploads and processing for input data and schema files.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        # Common delimiters to check for
        self.delimiters = [',', ';', '|', '\t']
        self.delimiter_names = {',': 'comma', ';': 'semicolon', '|': 'pipe', '\t': 'tab'}
        self._logger = logger or logging.getLogger(__name__)
    
    def _detect_delimiter(self, file_content, filename):
        """
        Detect the delimiter used in a CSV-like file.
        
        Args:
            file_content (str): Content of the file
            filename (str): Name of the file for debugging
            
        Returns:
            str: Detected delimiter, comma as fallback
        """
        self._logger.debug(f"Detecting delimiter for file: {filename}")
        
        # Get first few lines to analyze
        lines = file_content.strip().split('\n')
        if len(lines) == 0:
            self._logger.debug("File has no content, using comma as fallback")
            return ','
        
        # Use first line to detect delimiter
        first_line = lines[0]
        self._logger.debug(f"First line: {first_line[:100]}...")
        
        delimiter_scores = {}
        
        for delimiter in self.delimiters:
            try:
                # Try to parse with this delimiter
                df = pd.read_csv(StringIO(file_content), delimiter=delimiter, nrows=5)
                
                # Score based on multiple factors
                score = 0
                
                # Factor 1: Number of columns (more columns generally better)
                num_columns = len(df.columns)
                score += num_columns * 10
                
                # Factor 2: Consistent number of fields per row
                field_counts = [len(line.split(delimiter)) for line in lines[:5]]
                if len(set(field_counts)) == 1:  # All rows have same number of fields
                    score += 50
                
                # Factor 3: No empty or very short column names (indicates wrong delimiter)
                empty_cols = sum(1 for col in df.columns if str(col).strip() == '' or len(str(col).strip()) < 2)
                score -= empty_cols * 20
                
                # Factor 4: Reasonable column names (no weird characters)
                weird_cols = sum(1 for col in df.columns if any(char in str(col) for char in ['Unnamed:', 'nan']))
                score -= weird_cols * 15
                
                delimiter_scores[delimiter] = score
                self._logger.debug(f"Delimiter '{self.delimiter_names[delimiter]}' score: {score} (cols: {num_columns})")
                
            except Exception as e:
                delimiter_scores[delimiter] = -100  # Heavy penalty for parsing errors
                self._logger.debug(f"Delimiter '{self.delimiter_names[delimiter]}' failed: {str(e)[:50]}")
        
        # Find best delimiter
        best_delimiter = max(delimiter_scores.items(), key=lambda x: x[1])
        detected_delimiter = best_delimiter[0]
        best_score = best_delimiter[1]
        
        # If no delimiter scored well, fall back to comma
        if best_score < 0:
            self._logger.debug(f"No delimiter scored well (best: {best_score}), falling back to comma")
            detected_delimiter = ','
        else:
            self._logger.debug(f"Detected delimiter: '{self.delimiter_names[detected_delimiter]}' with score: {best_score}")
        
        return detected_delimiter
    
    def process_input_file(self, uploaded_file):
        """
        Process uploaded input files (CSV, TXT) with delimiter detection.
        
        Args:
            uploaded_file: Streamlit uploaded file object
            
        Returns:
            str: Processed file content as string
        """
        try:
            file_extension = uploaded_file.name.split('.')[-1].lower()
            self._logger.debug(f"Processing input file: {uploaded_file.name} (type: {file_extension})")
            
            if file_extension == 'csv':
                # Read file content first
                file_content = uploaded_file.getvalue().decode("utf-8")
                self._logger.debug(f"File content length: {len(file_content)}")
                
                # Detect delimiter
                delimiter = self._detect_delimiter(file_content, uploaded_file.name)
                
                # Read CSV with detected delimiter
                df = pd.read_csv(StringIO(file_content), delimiter=delimiter)
                self._logger.debug(f"CSV loaded with delimiter '{self.delimiter_names[delimiter]}', shape: {df.shape}")
                
                # Convert to standard comma-separated CSV string for consistency
                csv_string = df.to_csv(index=False, sep=',')
                self._logger.debug("Converted to standard CSV format (comma-separated)")
                return csv_string
                
            elif file_extension == 'txt':
                # For TXT files, also try delimiter detection in case it's a delimited file
                file_content = uploaded_file.getvalue().decode("utf-8")
                self._logger.debug(f"Text file loaded with length: {len(file_content)}")
                
                # Check if TXT file might be delimited data
                if self._might_be_delimited_data(file_content):
                    self._logger.debug("TXT file appears to contain delimited data")
                    delimiter = self._detect_delimiter(file_content, uploaded_file.name)
                    
                    try:
                        # Try to parse as delimited data
                        df = pd.read_csv(StringIO(file_content), delimiter=delimiter)
                        csv_string = df.to_csv(index=False, sep=',')
                        self._logger.debug(f"TXT file successfully parsed as delimited data with '{self.delimiter_names[delimiter]}'")
                        return csv_string
                    except Exception as e:
                        self._logger.error(f"Failed to parse TXT as delimited data: {str(e)}")
                        # Fall back to treating as plain text
                
                # Return as plain text
                return file_content
                
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
                
        except Exception as e:
            self._logger.error(f"Error processing input file: {str(e)}")
            st.error(f"Error processing input file: {str(e)}")
            return None
    
    def _might_be_delimited_data(self, content):
        """
        Check if text content might be delimited data.
        
        Args:
            content (str): File content
            
        Returns:
            bool: True if content might be delimited data
        """
        lines = content.strip().split('\n')
        if len(lines) < 2:
            return False
        
        # Check if multiple lines have delimiter characters
        delimiter_counts = {delim: 0 for delim in self.delimiters}
        
        for line in lines[:5]:  # Check first 5 lines
            for delim in self.delimiters:
                if delim in line and len(line.split(delim)) > 1:
                    delimiter_counts[delim] += 1
        
        # If any delimiter appears in most lines, it might be delimited data
        max_count = max(delimiter_counts.values())
        return max_count >= len(lines[:5]) * 0.6  # 60% of lines have delimiter
    
    def _detect_output_format_type(self, content):
        """
        Detect if the output format is a JSON schema or actual JSON data.
        
        Args:
            content (str): JSON content to analyze
            
        Returns:
            tuple: (format_type, confidence) where format_type is 'schema' or 'data'
        """
        try:
            parsed_json = json.loads(content)
            self._logger.debug("Analyzing output format type")
            
            # Schema indicators (keywords commonly found in JSON schemas)
            schema_keywords = {
                'type', 'properties', 'description', 'required', 'items', 
                'additionalProperties', 'enum', 'format', 'pattern', 
                'minimum', 'maximum', 'minLength', 'maxLength', 'title',
                '$schema', '$id', 'definitions', 'anyOf', 'oneOf', 'allOf'
            }
            
            # Data indicators (patterns suggesting actual data)
            data_indicators = 0
            schema_indicators = 0
            
            def analyze_object(obj, depth=0):
                nonlocal schema_indicators, data_indicators
                
                if depth > 3:  # Prevent deep recursion
                    return
                
                if isinstance(obj, dict):
                    # Check for schema keywords in keys
                    for key in obj.keys():
                        if key in schema_keywords:
                            schema_indicators += 2
                            self._logger.debug(f"Found schema keyword: '{key}'")
                    
                    # Check for schema patterns
                    if 'type' in obj and isinstance(obj['type'], str):
                        schema_indicators += 3
                    
                    if 'properties' in obj and isinstance(obj['properties'], dict):
                        schema_indicators += 3
                        
                    if 'description' in obj and isinstance(obj['description'], str):
                        schema_indicators += 2
                    
                    # Check for data patterns
                    if all(isinstance(v, (str, int, float, bool, type(None))) for v in obj.values()):
                        data_indicators += 1
                    
                    # Recurse into nested objects
                    for value in obj.values():
                        if isinstance(value, (dict, list)):
                            analyze_object(value, depth + 1)
                
                elif isinstance(obj, list):
                    # Arrays of similar objects suggest data
                    if len(obj) > 1:
                        first_item = obj[0] if obj else None
                        if isinstance(first_item, dict):
                            # Check if all items have similar structure (data pattern)
                            first_keys = set(first_item.keys()) if first_item else set()
                            similar_structure = all(
                                isinstance(item, dict) and 
                                len(set(item.keys()).symmetric_difference(first_keys)) <= 1
                                for item in obj[:5]  # Check first 5 items
                            )
                            if similar_structure:
                                data_indicators += 2
                                self._logger.debug(f"Found data array pattern with {len(obj)} items")
                    
                    # Recurse into list items
                    for item in obj[:3]:  # Check first 3 items
                        analyze_object(item, depth + 1)
            
            # Analyze the parsed JSON
            analyze_object(parsed_json)
            
            # Calculate confidence and determine type
            total_indicators = schema_indicators + data_indicators
            if total_indicators == 0:
                # No clear indicators, make educated guess based on structure
                if isinstance(parsed_json, dict) and len(parsed_json) < 10:
                    format_type = 'schema'
                    confidence = 0.3
                else:
                    format_type = 'data'
                    confidence = 0.3
            else:
                schema_confidence = schema_indicators / total_indicators
                if schema_confidence > 0.6:
                    format_type = 'schema'
                    confidence = schema_confidence
                else:
                    format_type = 'data'
                    confidence = 1 - schema_confidence
            
            self._logger.debug(f"Schema indicators: {schema_indicators}, Data indicators: {data_indicators}")
            self._logger.debug(f"Detected format type: {format_type} (confidence: {confidence:.2f})")
            
            return format_type, confidence
            
        except json.JSONDecodeError:
            self._logger.debug("Not valid JSON, treating as data example")
            return 'data', 0.5  # If not valid JSON, assume it's an example
        except Exception as e:
            self._logger.error(f"Error analyzing output format: {str(e)}")
            return 'data', 0.1  # Default to data with low confidence

    def process_schema_file(self, uploaded_file):
        """
        Process uploaded schema files (JSON) and detect if it's schema or data.
        
        Args:
            uploaded_file: Streamlit uploaded file object
            
        Returns:
            dict: Contains 'content', 'type', and 'confidence'
        """
        try:
            self._logger.debug(f"Processing schema file: {uploaded_file.name}")
            
            # Read JSON file
            content = json.load(uploaded_file)
            
            # Convert back to formatted JSON string
            json_string = json.dumps(content, indent=2)
            
            # Detect if it's schema or data
            format_type, confidence = self._detect_output_format_type(json_string)
            
            self._logger.debug(f"JSON file loaded with length: {len(json_string)}")
            self._logger.debug(f"Detected as {format_type} with confidence: {confidence:.2f}")
            
            return {
                'content': json_string,
                'type': format_type,
                'confidence': confidence
            }
            
        except json.JSONDecodeError as e:
            self._logger.error(f"JSON decode error: {str(e)}")
            st.error(f"Invalid JSON file: {str(e)}")
            return None
        except Exception as e:
            self._logger.error(f"Error processing schema file: {str(e)}")
            st.error(f"Error processing schema file: {str(e)}")
            return None
    
    def analyze_pasted_output_format(self, content):
        """
        Analyze pasted output format content to determine if it's schema or data.
        
        Args:
            content (str): Pasted content
            
        Returns:
            dict: Contains 'content', 'type', and 'confidence'
        """
        format_type, confidence = self._detect_output_format_type(content)
        
        return {
            'content': content,
            'type': format_type,
            'confidence': confidence
        }
    
    def validate_csv_data(self, csv_string):
        """
        Validate if CSV data is properly formatted.
        
        Args:
            csv_string: CSV data as string
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            df = pd.read_csv(StringIO(csv_string))
            self._logger.debug(f"CSV validation successful, shape: {df.shape}")
            return True
        except Exception as e:
            self._logger.error(f"CSV validation failed: {str(e)}")
            return False