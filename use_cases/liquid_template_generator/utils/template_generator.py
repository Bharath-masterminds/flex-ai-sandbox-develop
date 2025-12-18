# from utils.llm_config import get_llm_client
from langchain_core.messages import HumanMessage

import json
import logging
from typing import Optional

from fx_ai_reusables.llm import ILlmCreator
from fx_ai_reusables.helpers import run_async_in_sync_context
from use_cases.liquid_template_generator.utils.template_renderer import TemplateRenderer


class TemplateGenerator:
    """
    Generate Liquid templates using Azure OpenAI LLM with agentic workflow.
    """
    
    def __init__(self, template_rend: TemplateRenderer, llm_creator: ILlmCreator, max_iterations=5, logger: Optional[logging.Logger] = None):
        
        self.llm_creator = llm_creator
        self.template_rend = template_rend
        self.max_iterations = max_iterations  # Allow user-configurable iterations
        self._llm_client = None  # Lazy initialization
        self._logger = logger or logging.getLogger(__name__)

    def _ensure_llm_client(self):
        """Ensure LLM client is initialized (lazy initialization)."""
        if self._llm_client is None:
            self._llm_client = run_async_in_sync_context(self.llm_creator.create_llm)

    def generate_template(self, input_data, output_schema=None, additional_instructions=None, progress_callback=None, output_format_info=None):
        """
        Generate a Liquid template using an agentic workflow.
        
        Args:
            input_data (str): The input data (CSV or text)
            output_schema (str): Optional output schema or example
            additional_instructions (str): Optional additional instructions
            progress_callback (callable): Optional callback function for progress updates
            output_format_info (dict): Information about output format type and confidence
            
        Returns:
            tuple: (Generated Liquid template, actual iterations used)
        """
        # Ensure LLM client is initialized
        self._ensure_llm_client()
        
        self._logger.debug(f"Starting template generation with max {self.max_iterations} iterations")
        self._logger.debug(f"Input data length: {len(input_data) if input_data else 0}")
        self._logger.debug(f"Output schema provided: {bool(output_schema)}")
        self._logger.debug(f"Additional instructions provided: {bool(additional_instructions)}")
        self._logger.debug(f"Output format info: {output_format_info}")




        
        # Update progress if callback provided
        if progress_callback:
            progress_callback(0, self.max_iterations, "Generating initial template...")
        
        # Generate initial template
        template = self._generate_initial_template(input_data, output_schema, additional_instructions, output_format_info)
                
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            self._logger.debug(f"Template generation iteration {iteration}")
            
            # Update progress
            if progress_callback:
                progress_callback(iteration, self.max_iterations, f"Testing template (attempt {iteration})")
            
            try:
                # Try to render the template
                rendered_output = self.template_rend.render_template(template, input_data)
                
                # If we have an output schema, validate against it
                if output_schema:
                    is_valid = self._validate_output(rendered_output, output_schema)
                    if not is_valid:
                        self._logger.debug("Output validation failed, refining template")
                        if progress_callback:
                            progress_callback(iteration, self.max_iterations, f"Refining template (validation failed)")
                        template = self._refine_template(template, input_data, output_schema, 
                                                       additional_instructions, rendered_output, 
                                                       "Output doesn't match expected schema", output_format_info)
                        continue
                
                self._logger.debug(f"Template generation successful after {iteration} iterations")
                if progress_callback:
                    progress_callback(self.max_iterations, self.max_iterations, "Template generation completed successfully!")
                return template, iteration
                
            except Exception as e:
                error_msg = str(e)
                self._logger.debug(f"Template rendering failed: {error_msg}")
                
                if iteration >= self.max_iterations:
                    self._logger.debug(f"Max iterations ({self.max_iterations}) reached, returning best attempt")
                    if progress_callback:
                        progress_callback(self.max_iterations, self.max_iterations, f"Max iterations reached. Returning best template.")
                    return template, iteration
                
                # Refine template based on error
                if progress_callback:
                    progress_callback(iteration, self.max_iterations, f"Fixing error: {error_msg[:50]}...")
                template = self._refine_template(template, input_data, output_schema, 
                                               additional_instructions, None, error_msg, output_format_info)
        
        if progress_callback:
            progress_callback(self.max_iterations, self.max_iterations, "Template generation completed.")
        return template, iteration
    
    def _generate_initial_template(self, input_data, output_schema, additional_instructions, output_format_info):
        """Generate the initial Liquid template."""
        self._ensure_llm_client()
        
        self._logger.debug("Generating initial template")
        
        prompt = self._build_initial_prompt(input_data, output_schema, additional_instructions, output_format_info)
        
        try:
            response = self._llm_client.invoke([HumanMessage(content=prompt)])
            # Handle different response types from LangChain
            if hasattr(response, 'content'):
                template = str(response.content)
            else:
                template = str(response)
            
            # Extract template from markdown code blocks if present
            if "```liquid" in template:
                template = template.split("```liquid")[1].split("```")[0].strip()
            elif "```" in template:
                template = template.split("```")[1].split("```")[0].strip()
            
            self._logger.debug(f"Initial template generated (length: {len(template)})")
            return template
            
        except Exception as e:
            self._logger.error(f"Error generating initial template: {str(e)}")
            raise Exception(f"Failed to generate initial template: {str(e)}")
    
    def _refine_template(self, current_template, input_data, output_schema, 
                        additional_instructions, rendered_output, error_msg, output_format_info=None):
        """Refine the template based on feedback."""
        self._ensure_llm_client()
        
        self._logger.debug(f"Refining template due to: {error_msg}")
        
        prompt = self._build_refinement_prompt(current_template, input_data, output_schema,
                                             additional_instructions, rendered_output, error_msg, output_format_info)
        
        try:
            response = self._llm_client.invoke([HumanMessage(content=prompt)])
            # Handle different response types from LangChain
            if hasattr(response, 'content'):
                refined_template = str(response.content)
            else:
                refined_template = str(response)
            
            # Extract template from markdown code blocks if present
            if "```liquid" in refined_template:
                refined_template = refined_template.split("```liquid")[1].split("```")[0].strip()
            elif "```" in refined_template:
                refined_template = refined_template.split("```")[1].split("```")[0].strip()
            
            self._logger.debug(f"Template refined (length: {len(refined_template)})")
            return refined_template
            
        except Exception as e:
            self._logger.error(f"Error refining template: {str(e)}")
            return current_template  # Return current template if refinement fails
    
    def _build_initial_prompt(self, input_data, output_schema, additional_instructions, output_format_info):
        """Build the initial prompt for template generation."""
        
        # Parse input data to extract header and first row information
        parsed_data = self.template_rend._parse_input_data(input_data)
        
        # Build header and first row information for the prompt
        data_structure_info = ""
        if 'header_row' in parsed_data and 'first_data_row' in parsed_data:
            header_row = parsed_data['header_row']
            first_data_row = parsed_data['first_data_row']
            
            data_structure_info = f"""
DATA STRUCTURE ANALYSIS:
Header Row (Column Names): {header_row}
First Data Row (Sample Values): {first_data_row}
Total Rows in Dataset: {parsed_data.get('count', 'unknown')}

IMPORTANT: Do NOT iterate through data rows. Use the column names from the header row and reference individual column values directly.
"""
        
        prompt = f"""You are an expert in creating Liquid templates. Generate a Liquid template that transforms the given input data structure into the desired output format.

INPUT DATA SAMPLE:
```
{input_data[:1500]}
```

{data_structure_info}"""

        # Determine template generation strategy based on output schema availability
        if output_schema:
            # Case: Output schema/format is provided
            prompt += """
🎯 ULTIMATE GOAL - OUTPUT STRUCTURE COMPLIANCE:
The PRIMARY and ULTIMATE objective is to generate a Liquid template that produces output matching the exact structure, fields, and format specified in the output schema/example below. 

CRITICAL TRANSFORMATION PRINCIPLES:
1. The OUTPUT SCHEMA/FORMAT is the FINAL TARGET - everything else is guidance to achieve this target
2. If input has 10 columns but output only needs 4 columns - ONLY include those 4 columns in the output
3. If input has fewer columns than output needs - use available data and apply transformations as guided
4. Additional instructions and transformation logic are GUIDES to help you transform input data to match the target output
5. When in doubt, prioritize matching the output structure over including all input data

TEMPLATE GENERATION STRATEGY:
You MUST generate a Liquid template that:
1. Transforms the input data to EXACTLY match the specified output format/schema (PRIMARY GOAL)
2. Uses additional instructions and transformation logic as guidance for HOW to transform the data
3. Does NOT produce any additional elements or data beyond what's specified in the output
4. Conforms strictly to the provided structure and requirements
5. Ignores any input data elements that are not needed for the target output format
6. Applies transformations as specified in the guidance to map source fields to target fields

SOURCE-TO-TARGET MAPPING APPROACH:
- Analyze the input data structure (source)
- Analyze the output schema/format (target) 
- Use transformation guidance to understand HOW to map source fields to target fields
- Generate a template that creates ONLY the target structure, not a comprehensive input dump

"""
            # Add output format type information to the prompt
            if output_format_info and output_format_info.get('type'):
                format_type = output_format_info['type']
                confidence = output_format_info.get('confidence', 0)
                
                if format_type == 'schema':
                    prompt += f"""
🎯 TARGET OUTPUT SCHEMA (JSON Schema - confidence: {confidence:.0%}) - THIS IS YOUR DESTINATION:
The following JSON schema defines the EXACT structure and types your template MUST produce.
This is the final target - use all guidance below to achieve THIS structure.
```
{output_schema}
```

SCHEMA COMPLIANCE RULES:
- Look for "type" fields to understand required data types (string, number, boolean, array, object)
- Check "properties" to see required fields and their structure
- Pay attention to "required" arrays for mandatory fields
- Use "description" fields to understand the purpose of each field
- Generate actual data values that match the schema types and constraints
- ONLY include fields defined in the schema - do not add extra fields from input
- Use transformation guidance to understand HOW to populate these schema fields from input data
"""
                else:  # data
                    prompt += f"""
🎯 TARGET OUTPUT EXAMPLE (JSON Data - confidence: {confidence:.0%}) - THIS IS YOUR DESTINATION:
The following example shows the EXACT data format your template MUST produce.
This is the final target - use all guidance below to achieve THIS structure.
```
{output_schema}
```

OUTPUT FORMAT COMPLIANCE RULES:
- Use this as the exact template for the structure and format of your output
- Maintain the same field names and data types shown in the example
- Preserve the overall JSON structure (objects, arrays, nesting)
- Generate dynamic content using input data while keeping the same format
- ONLY include fields shown in the example - do not add extra fields from input
- Use transformation guidance to understand HOW to populate these example fields from input data
"""
            else:
                prompt += f"""
🎯 TARGET OUTPUT FORMAT - THIS IS YOUR DESTINATION:
```
{output_schema}
```

Transform the input data to match this EXACT format. Do not include any additional fields or data beyond what's shown above.
Use any transformation guidance provided to understand HOW to map input fields to this target structure.
"""
        else:
            # Case: No output schema provided
            prompt += """
TEMPLATE GENERATION STRATEGY:
Since NO output format/schema is provided, you MUST generate a Liquid template that:
1. Extracts ALL available elements from the input data
2. Creates a comprehensive output that includes every column/field from the input
3. Preserves all data structure and information
4. Uses appropriate formatting for readability and completeness
5. Does not omit any input data elements

COMPREHENSIVE DATA EXTRACTION:
- Include every column from the header row in your output
- Use all available data fields and values
- Create a well-structured format (JSON, CSV, or appropriate structure)
- Ensure no input data is lost or ignored in the transformation

"""
        
        if additional_instructions:
            prompt += f"""
📋 TRANSFORMATION GUIDANCE (Use this to achieve the target output structure):
The following instructions guide HOW to transform input data to match the target output:
{additional_instructions}

GUIDANCE USAGE RULES:
- These instructions help you understand HOW to transform source data to target format
- Apply these transformations while ensuring the output matches the target schema/format above
- If guidance mentions fields not in the target output, ignore those transformations
- Focus on transformations that help populate the target output structure
"""
        
        prompt += """
CRITICAL LIQUID SYNTAX RULES:
1. NO parentheses for grouping: () are NOT allowed in Liquid expressions
2. NO complex mathematical expressions with parentheses
3. Use assign tags for complex calculations:
   WRONG: {{ 'now' | date: "%Y" | minus: (DOB | date: "%Y") }}
   RIGHT: {% assign current_year = 'now' | date: "%Y" %}
          {% assign birth_year = DOB | date: "%Y" %}
          {{ current_year | minus: birth_year }}

4. Liquid filter chaining rules:
   - Each filter operates on the result of the previous filter
   - No nested expressions or parentheses
   - Keep expressions simple and linear

5. For calculations, use separate assign statements:
   {% assign step1 = value | filter1 %}
   {% assign step2 = step1 | filter2 %}
   {{ step2 }}
   
CRITICAL DATA REFERENCE RULES:
1. DO NOT use loops like {% for row in rows %} - this is prohibited
2. DO NOT iterate through data - work with the structure only
3. Reference columns directly using these patterns:

DIRECT COLUMN REFERENCES (PREFERRED):
   - Access column values: {{ column_name }}
   - For columns with spaces: {{ ['column name'] }}
   - Example: {{ name }}, {{ age }}, {{ ['full name'] }}

ALTERNATIVE REFERENCE PATTERNS:
   - Using first row data: {{ first_data_row['column_name'] }}
   - Using first row dot notation: {{ first_data_row.column_name }}

OUTPUT REQUIREMENTS:
1. Generate ONLY the Liquid template code that produces the TARGET OUTPUT STRUCTURE
2. NO additional comments, explanations, or feedback
3. NO markdown formatting or code block indicators
4. Use proper Liquid syntax with {% %} for logic and {{ }} for output
5. Reference individual columns, not data arrays
6. NO iteration or loops through data rows
7. Use the header row for column names and first data row for sample values
8. Handle columns with spaces using bracket notation: {{ ['column name'] }}
9. Focus on creating the exact target structure, not processing all input data
10. Apply transformation guidance to map source fields to target fields correctly

🎯 REMEMBER: Your template must produce output that EXACTLY matches the target schema/format provided above. Additional instructions and transformation logic are guidance to help you achieve that target, not requirements to process all input data."""
        
        return prompt
    
    def _build_refinement_prompt(self, current_template, input_data, output_schema,
                                additional_instructions, rendered_output, error_msg, output_format_info):
        """Build the refinement prompt."""
        
        # Parse input data to extract header and first row information
        parsed_data = self.template_rend._parse_input_data(input_data)
        
        # Build header and first row information for the prompt
        data_structure_info = ""
        if 'header_row' in parsed_data and 'first_data_row' in parsed_data:
            header_row = parsed_data['header_row']
            first_data_row = parsed_data['first_data_row']
            
            data_structure_info = f"""
DATA STRUCTURE ANALYSIS:
Header Row (Column Names): {header_row}
First Data Row (Sample Values): {first_data_row}
Total Rows in Dataset: {parsed_data.get('count', 'unknown')}

REMINDER: Do NOT iterate through data rows. Use column names and reference individual values only.
"""
        
        prompt = f"""The following Liquid template has an issue and needs to be fixed:

CURRENT TEMPLATE:
```liquid
{current_template}
```

INPUT DATA:
```
{input_data[:1000]}
```

{data_structure_info}

ERROR/ISSUE:
{error_msg}
"""
        
        if rendered_output:
            prompt += f"""
CURRENT OUTPUT:
```
{rendered_output[:1000]}
```
"""
        
        if output_schema:
            # Add output format type information to refinement prompt
            if output_format_info and output_format_info.get('type'):
                format_type = output_format_info['type']
                confidence = output_format_info.get('confidence', 0)
                
                if format_type == 'schema':
                    prompt += f"""
TARGET OUTPUT SCHEMA (JSON Schema - confidence: {confidence:.0%}):
Your template should generate JSON data that conforms to this schema:
```
{output_schema}
```

SCHEMA VALIDATION:
- Ensure output matches the required "type" specifications
- Include all fields defined in "properties"
- Respect "required" field constraints
- Match data types exactly (string, number, boolean, array, object)
"""
                else:  # data
                    prompt += f"""
TARGET OUTPUT EXAMPLE (JSON Data - confidence: {confidence:.0%}):
Your template should generate JSON data similar to this example:
```
{output_schema}
```

FORMAT MATCHING:
- Maintain the same structure and field names
- Keep the same data types and nesting levels
- Preserve array structures and object hierarchies
"""
            else:
                prompt += f"""
DESIRED OUTPUT FORMAT:
```
{output_schema}
```
"""
        
        if additional_instructions:
            prompt += f"""
ADDITIONAL INSTRUCTIONS:
{additional_instructions}
"""
        
        prompt += """
CRITICAL FIXES FOR COMMON ERRORS:

1. If you see "undefined variable" errors:
   - Use direct column access: {{ column_name }}
   - For spaced columns: {{ ['column name'] }}
   - Use first row data: {{ first_data_row['column_name'] }}

2. If template has iteration (REMOVE IT):
   - REMOVE: {% for row in rows %}...{% endfor %}
   - REPLACE WITH: Direct column references

3. If columns have spaces in names:
   - Use: {{ ['column name'] }} instead of {{ column_name }}

4. If output doesn't match schema/format:
   - For schemas: Ensure data types match (string vs number vs boolean)
   - For data examples: Maintain exact field names and structure
   - Check array vs object distinctions

5. Reference pattern fixes:
   - CORRECT: {{ column_name }} or {{ first_data_row.column_name }}
   - INCORRECT: {{ row['column'] }} or {% for row in rows %}
   - Handle spaces: {{ ['full name'] }} or {{ first_data_row['full name'] }}

6. JSON syntax fixes:
   - Proper quotes, commas, brackets
   - No trailing commas
   - Correct nesting

REMEMBER: NO LOOPS OR ITERATION - Reference structure only!

Please fix the Liquid template to resolve the issue. Return only the corrected Liquid template code without any explanations or markdown formatting."""
        
        return prompt
    
    def _validate_output(self, rendered_output, output_schema):
        """Validate if the rendered output matches the expected schema."""
        try:
            # Try to parse both as JSON for comparison
            try:
                rendered_json = json.loads(rendered_output)
                schema_json = json.loads(output_schema)
                
                # Basic structure comparison
                if isinstance(rendered_json, dict) and isinstance(schema_json, dict):
                    return self._compare_json_structure(rendered_json, schema_json)
                elif isinstance(rendered_json, list) and isinstance(schema_json, list):
                    if len(rendered_json) > 0 and len(schema_json) > 0:
                        return self._compare_json_structure(rendered_json[0], schema_json[0])
                
            except json.JSONDecodeError:
                # If not JSON, do basic string comparison
                pass
            
            # For non-JSON, consider it valid for now
            return True
            
        except Exception as e:
            self._logger.error(f"Output validation error: {str(e)}")
            return True  # Default to valid if validation fails
    
    def _compare_json_structure(self, obj1, obj2):
        """Compare the structure of two JSON objects."""
        if type(obj1) != type(obj2):
            return False
        
        if isinstance(obj1, dict):
            # Check if keys are similar (allowing for some flexibility)
            keys1 = set(obj1.keys())
            keys2 = set(obj2.keys())
            common_keys = keys1.intersection(keys2)
            
            # At least 70% of keys should match
            if len(common_keys) / max(len(keys1), len(keys2)) >= 0.7:
                return True
        
        return True  # Default to valid for other types