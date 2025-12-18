from liquid import Environment
import pandas as pd
import json
import re
import logging
from io import StringIO
from typing import Optional

class TemplateRenderer:
    """
    Render Liquid templates with input data.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.env = Environment()
        self._logger = logger or logging.getLogger(__name__)
        self._logger.debug("Template renderer initialized")
    
    def render_template(self, template_string, input_data):
        """
        Render a Liquid template with the provided input data.
        
        Args:
            template_string (str): The Liquid template
            input_data (str): Input data as string (CSV or text)
            
        Returns:
            str: Rendered output
        """
        self._logger.debug("Starting template rendering")
        self._logger.debug(f"Template length: {len(template_string)}")
        self._logger.debug(f"Input data length: {len(input_data)}")
        
        try:
            # Parse the input data
            base_data = self._parse_input_data(input_data)
            self._logger.debug("Input data parsed successfully")
            
            # Analyze template to determine reference pattern
            reference_pattern = self._analyze_template_references(template_string)
            self._logger.debug(f"Template reference pattern: {reference_pattern}")
            
            # Prepare data based on reference pattern
            template_data = self._prepare_template_data(base_data, reference_pattern, template_string)
            self._logger.debug(f"Template data prepared with keys: {list(template_data.keys())}")
            
            # Create Liquid template
            template = self.env.from_string(template_string)
            self._logger.debug("Liquid template created successfully")
            
            # Render the template
            rendered_output = template.render(**template_data)
            self._logger.debug(f"Template rendered successfully, output length: {len(rendered_output)}")
            
            return rendered_output
            
        except Exception as e:
            error_msg = f"Template rendering failed: {str(e)}"
            self._logger.error(error_msg)
            raise Exception(error_msg)
    
    def _analyze_template_references(self, template_string):
        """
        Analyze the template to determine how data is being referenced.
        
        Args:
            template_string (str): The Liquid template
            
        Returns:
            str: Reference pattern ('row_based', 'direct_reference', 'mixed')
        """
        # Check for row['column'] or row.column patterns
        row_bracket_pattern = r'row\[[\'"]\w+[\'"]\]'
        row_dot_pattern = r'row\.\w+'
        
        # Check for direct {{ column }} or {{ ['column name'] }} patterns
        direct_bracket_pattern = r'\{\{\s*[\'"]\w+[^}]*[\'"]\s*\}\}'
        direct_variable_pattern = r'\{\{\s*\w+\s*\}\}'
        spaced_column_pattern = r'\{\{\s*\[[\'""][^}]+[\'""]\]\s*\}\}'
        
        has_row_references = (
            re.search(row_bracket_pattern, template_string) or 
            re.search(row_dot_pattern, template_string)
        )
        
        has_direct_references = (
            re.search(direct_variable_pattern, template_string) or
            re.search(direct_bracket_pattern, template_string) or
            re.search(spaced_column_pattern, template_string)
        )
        
        self._logger.debug(f"Has row references: {has_row_references}")
        self._logger.debug(f"Has direct references: {has_direct_references}")
        
        if has_row_references and has_direct_references:
            return 'mixed'
        elif has_row_references:
            return 'row_based'
        else:
            return 'direct_reference'
    
    def _prepare_template_data(self, base_data, reference_pattern, template_string):
        """
        Prepare data for template rendering based on reference pattern.
        
        Args:
            base_data (dict): Parsed input data
            reference_pattern (str): How data is referenced in template
            template_string (str): The template string for additional analysis
            
        Returns:
            dict: Data prepared for template rendering
        """
        if reference_pattern == 'row_based':
            # For row['column'] or row.column patterns
            return self._prepare_row_based_data(base_data)
        elif reference_pattern == 'direct_reference':
            # For {{ column }} patterns
            return self._prepare_direct_reference_data(base_data, template_string)
        else:  # mixed
            # For mixed patterns, provide both formats
            row_data = self._prepare_row_based_data(base_data)
            direct_data = self._prepare_direct_reference_data(base_data, template_string)
            
            # Merge both formats
            combined_data = {**row_data, **direct_data}
            return combined_data
    
    def _prepare_row_based_data(self, base_data):
        """
        Prepare data for row-based references (row['column'] or row.column).
        
        Args:
            base_data (dict): Parsed input data
            
        Returns:
            dict: Data with row-based structure
        """
        self._logger.debug("Preparing row-based data")
        
        if 'rows' in base_data and base_data['rows']:
            # For CSV data, iterate through each row
            template_data = base_data.copy()
            
            # Add individual row access for loops
            if len(base_data['rows']) > 0:
                # Provide access to the first row as an example
                template_data['row'] = base_data['rows'][0]
            
            return template_data
        else:
            # For non-CSV data, create a single row structure
            return {
                'row': base_data,
                **base_data
            }
    
    def _prepare_direct_reference_data(self, base_data, template_string):
        """
        Prepare data for direct references ({{ column }} or {{ ['column name'] }}).
        
        Args:
            base_data (dict): Parsed input data
            template_string (str): Template string to extract column references
            
        Returns:
            dict: Data with direct column access
        """
        self._logger.debug("Preparing direct reference data")
        
        if 'rows' in base_data and base_data['rows']:
            # For CSV data, extract all unique column values
            df = pd.DataFrame(base_data['rows'])
            template_data = base_data.copy()
            
            # Add each column as a direct variable
            for col in df.columns:
                # Original column name (for exact matches)
                template_data[col] = df[col].tolist()
                
                # Handle spaced column names with bracket notation
                # Extract {{ ['column name'] }} patterns from template
                spaced_pattern = r'\{\{\s*\[[\'""]([^}]+)[\'""]\]\s*\}\}'
                spaced_matches = re.findall(spaced_pattern, template_string)
                
                for spaced_col in spaced_matches:
                    if spaced_col == col:
                        # Create a safe key for spaced column names
                        safe_key = f"_spaced_{col.replace(' ', '_').replace('-', '_')}"
                        template_data[safe_key] = df[col].tolist()
                        self._logger.debug(f"Added spaced column mapping: '{col}' -> '{safe_key}'")
                
                # Clean column name for Liquid (for compatibility)
                clean_col = str(col).replace(' ', '_').replace('-', '_').replace('.', '_')
                clean_col = ''.join(c for c in clean_col if c.isalnum() or c == '_')
                if clean_col != col:
                    template_data[clean_col] = df[col].tolist()
            
            return template_data
        else:
            # For non-CSV data, return as-is
            return base_data
    
    def _parse_input_data(self, input_data):
        """
        Parse input data and convert it to a format suitable for Liquid templates.
        
        Args:
            input_data (str): Raw input data
            
        Returns:
            dict: Parsed data for template rendering
        """
        self._logger.debug("Parsing input data")
        
        # Try to detect if it's CSV data
        if self._is_csv_data(input_data):
            return self._parse_csv_data(input_data)
        else:
            return self._parse_text_data(input_data)
    
    def _is_csv_data(self, data):
        """Check if the data appears to be CSV format and detect delimiter."""
        try:
            # Look for common CSV indicators
            lines = data.strip().split('\n')
            if len(lines) < 2:
                return False
            
            # Check multiple delimiters
            delimiters = [',', ';', '|', '\t']
            delimiter_names = {',': 'comma', ';': 'semicolon', '|': 'pipe', '\t': 'tab'}
            
            best_delimiter = ','
            best_score = -1
            
            for delimiter in delimiters:
                try:
                    # Try to parse with this delimiter
                    df = pd.read_csv(StringIO(data), delimiter=delimiter)
                    
                    if len(df) > 0 and len(df.columns) > 1:
                        # Score based on consistency and column count
                        score = len(df.columns) * 10
                        
                        # Check field consistency
                        field_counts = [len(line.split(delimiter)) for line in lines[:5]]
                        if len(set(field_counts)) == 1:
                            score += 50
                        
                        # Penalize empty or weird column names
                        empty_cols = sum(1 for col in df.columns if str(col).strip() == '' or len(str(col).strip()) < 2)
                        score -= empty_cols * 20
                        
                        if score > best_score:
                            best_score = score
                            best_delimiter = delimiter
                        
                        self._logger.debug(f"Delimiter '{delimiter_names[delimiter]}' score: {score} for pasted data")
                except:
                    continue
            
            # Store detected delimiter for use in parsing
            self._detected_delimiter = best_delimiter
            self._logger.debug(f"Best delimiter for pasted data: '{delimiter_names[best_delimiter]}' (score: {best_score})")
            
            return best_score > 0
            
        except Exception:
            return False
    
    def _parse_csv_data(self, csv_data):
        """Parse CSV data into a dictionary for Liquid template."""
        self._logger.debug("Parsing as CSV data")
        
        try:
            # Use detected delimiter if available, otherwise comma
            delimiter = getattr(self, '_detected_delimiter', ',')
            delimiter_names = {',': 'comma', ';': 'semicolon', '|': 'pipe', '\t': 'tab'}
            
            self._logger.debug(f"Using delimiter: '{delimiter_names.get(delimiter, 'unknown')}'")
            
            df = pd.read_csv(StringIO(csv_data), delimiter=delimiter)
            
            # Extract header row and first data row for template generation
            header_row = df.columns.tolist()
            first_data_row = df.iloc[0].to_dict() if len(df) > 0 else {}
            
            self._logger.debug(f"Header row: {header_row}")
            self._logger.debug(f"First data row: {first_data_row}")
            
            # Convert DataFrame to dictionary
            # Focus on header and first row instead of all data
            data = {
                'header_row': header_row,           # Column names
                'first_data_row': first_data_row,   # First row values
                'columns': header_row,              # Alias for backward compatibility
                'count': len(df),                   # Total number of rows
                'delimiter_used': delimiter_names.get(delimiter, 'unknown'),  # Delimiter info
                'sample_data': df.head(3).to_dict('records')  # First 3 rows for reference
            }
            
            # Add individual columns as single values from first row
            for col in df.columns:
                # Clean column name for Liquid (remove spaces, special chars)
                clean_col = str(col).replace(' ', '_').replace('-', '_').replace('.', '_')
                clean_col = ''.join(c for c in clean_col if c.isalnum() or c == '_')
                
                # Store first row value for this column
                if len(df) > 0:
                    data[clean_col] = df[col].iloc[0]
                    # Also store original column name mapping
                    data[f"column_{clean_col}"] = col
            
            self._logger.debug(f"CSV parsed with '{delimiter_names.get(delimiter)}' - {len(df)} rows, {len(df.columns)} columns")
            self._logger.debug(f"Template will use header: {header_row} and first row: {first_data_row}")
            
            return data
            
        except Exception as e:
            self._logger.error(f"CSV parsing failed: {str(e)}")
            # Fall back to text parsing
            return self._parse_text_data(csv_data)
    
    def _parse_text_data(self, text_data):
        """Parse text data into a dictionary for Liquid template."""
        self._logger.debug("Parsing as text data")
        
        try:
            # Try to parse as JSON first
            try:
                json_data = json.loads(text_data)
                self._logger.debug("Text parsed as JSON")
                return {
                    'data': json_data,
                    'text': text_data,
                    'is_json': True
                }
            except json.JSONDecodeError:
                pass
            
            # Parse as plain text
            lines = text_data.strip().split('\n')
            
            data = {
                'text': text_data,
                'lines': lines,
                'line_count': len(lines),
                'is_json': False
            }
            
            # Try to extract key-value pairs if it looks like structured text
            key_value_pairs = {}
            for line in lines:
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # Clean key for Liquid
                        clean_key = key.replace(' ', '_').replace('-', '_').replace('.', '_')
                        clean_key = ''.join(c for c in clean_key if c.isalnum() or c == '_')
                        key_value_pairs[clean_key] = value
            
            if key_value_pairs:
                data['properties'] = key_value_pairs
                self._logger.debug(f"Extracted {len(key_value_pairs)} key-value pairs")
            
            self._logger.debug(f"Text parsed - {len(lines)} lines")
            return data
            
        except Exception as e:
            self._logger.error(f"Text parsing failed: {str(e)}")
            # Minimal fallback
            return {
                'text': text_data,
                'raw': text_data
            }
    
    def validate_template_syntax(self, template_string):
        """
        Validate if a Liquid template has correct syntax.
        
        Args:
            template_string (str): The Liquid template to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            template = self.env.from_string(template_string)
            return True, None
        except Exception as e:
            return False, str(e)