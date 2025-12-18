"""
Prompt Builder Service - Builds prompts by injecting inputs into templates.
"""
import logging
from pathlib import Path
from typing import List, Optional

from exceptions import PromptBuildError, ValidationError
from utils.validators import validate_identifier, validate_required_string


class PromptBuilderService:
    """Handles building prompts from templates and input data."""
    
    def __init__(self, prompts_dir: str = "prompts", logger: Optional[logging.Logger] = None):
        """
        Initialize the prompt builder.
        
        Args:
            prompts_dir: Directory containing prompt template files
            logger: Optional logger instance
            
        Raises:
            PromptBuildError: If prompts directory cannot be created
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Resolve prompts directory relative to use case root
        use_case_root = Path(__file__).parent.parent
        self.prompts_dir = use_case_root / prompts_dir
        
        try:
            if not self.prompts_dir.exists():
                self.prompts_dir.mkdir(parents=True, exist_ok=True)
                self.logger.warning(f"Created missing prompts directory: {self.prompts_dir}")
            else:
                self.logger.info(f"Initialized PromptBuilderService with prompts directory: {self.prompts_dir}")
        except PermissionError as e:
            error_msg = f"Permission denied creating prompts directory at {self.prompts_dir}: {e}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error creating prompts directory at {self.prompts_dir}: {e}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
    
    def _validate_identifier(self, identifier: str, field_name: str) -> None:
        """Validate an identifier using shared validation logic."""
        try:
            validate_identifier(identifier, field_name)
        except ValidationError as e:
            self.logger.error(str(e))
            raise
    
    def _validate_string_input(self, input_str: str, field_name: str) -> None:
        """Validate a required string input using shared validation logic."""
        try:
            validate_required_string(input_str, field_name)
        except ValidationError as e:
            self.logger.error(str(e))
            raise
    
    def _read_template(self, template_path: Path) -> str:
        """
        Read a prompt template from a file.
        
        Args:
            template_path: Path to the template file
            
        Returns:
            Template content as string
            
        Raises:
            PromptBuildError: If template cannot be read
        """
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError as e:
            error_msg = f"Prompt template not found: {template_path}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
        except PermissionError as e:
            error_msg = f"Permission denied reading template: {template_path}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
        except Exception as e:
            error_msg = f"Error reading template {template_path}: {e}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
    
    def build_liquid_to_mapping_prompt(
        self,
        resource_name: str,
        ig_name: str,
        ig_version: str,
        backend_source: str,
        input_json: str,
        liquid_mapping: str
    ) -> str:
        """
        Build a prompt for generating mapping table documentation FROM a liquid template.
        
        Args:
            resource_name: Name of the FHIR resource
            ig_name: Name of the Implementation Guide
            ig_version: Version of the Implementation Guide
            backend_source: Name of the backend source system
            input_json: Target FHIR JSON structure
            liquid_mapping: Liquid mapping template to document
            
        Returns:
            Complete prompt for generating mapping table documentation
        """
        template_path = self.prompts_dir / "liquid_to_mapping_table_prompt.md"
        
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # Replace placeholders
            prompt = template.replace("{resource_name}", resource_name)
            prompt = prompt.replace("{ig_name}", ig_name)
            prompt = prompt.replace("{ig_version}", ig_version)
            prompt = prompt.replace("{backend_source}", backend_source)
            prompt = prompt.replace("{input_json}", input_json)
            prompt = prompt.replace("{liquid_mapping}", liquid_mapping)
            
            return prompt
        else:
            # Fallback inline prompt if template not found
            return self._build_inline_liquid_to_mapping_prompt(
                resource_name, ig_name, ig_version, backend_source, input_json, liquid_mapping
            )
    
    def build_mapping_table_prompt(
        self,
        resource_name: str,
        ig_name: str,
        ig_version: str,
        backend_source: str,
        input_json: str,
        extra_context: Optional[str] = None,
        reference_mappings: Optional[List[str]] = None,
        additional_info: Optional[str] = None
    ) -> str:
        """
        Build a prompt for generating a mapping table FROM input JSON.
        
        Args:
            resource_name: Name of the FHIR resource
            ig_name: Name of the Implementation Guide
            ig_version: Version of the Implementation Guide
            backend_source: Name of the backend source system
            input_json: Input JSON data structure (source data)
            extra_context: Additional context for the resource (optional)
            reference_mappings: List of reference mapping table contents (optional)
            additional_info: User-provided additional information/context (optional)
            
        Returns:
            Complete prompt for generating mapping table
            
        Raises:
            ValidationError: If required inputs are invalid
            PromptBuildError: If prompt cannot be built
        """
        # Validate required inputs
        self._validate_identifier(resource_name, "resource_name")
        self._validate_identifier(ig_name, "ig_name")
        self._validate_identifier(ig_version, "ig_version")
        self._validate_identifier(backend_source, "backend_source")
        self._validate_string_input(input_json, "input_json")
        
        self.logger.info(f"Building mapping table prompt for {resource_name} ({ig_name} {ig_version}, {backend_source})")
        self.logger.debug(f"Input JSON length: {len(input_json)} bytes, "
                         f"extra_context: {bool(extra_context)}, "
                         f"reference_mappings: {len(reference_mappings) if reference_mappings else 0}, "
                         f"additional_info: {bool(additional_info)}")
        
        try:
            template_path = self.prompts_dir / "mapping_table_generation_prompt.md"
        
            if template_path.exists():
                self.logger.debug(f"Loading prompt template from: {template_path}")
                template = self._read_template(template_path)
                
                # Replace placeholders
                prompt = template.replace("{resource_name}", resource_name)
                prompt = prompt.replace("{ig_name}", ig_name)
                prompt = prompt.replace("{ig_version}", ig_version)
                prompt = prompt.replace("{backend_source}", backend_source)
                prompt = prompt.replace("{input_json}", input_json)
                
                # Add extra context if provided
                if extra_context:
                    self.logger.debug(f"Adding extra context: {len(extra_context)} characters")
                    prompt = prompt.replace("{extra_context}", f"\n\n## Extra Context:\n{extra_context}\n")
                else:
                    prompt = prompt.replace("{extra_context}", "")
                
                # Add reference mappings if provided
                if reference_mappings and len(reference_mappings) > 0:
                    self.logger.debug(f"Adding {len(reference_mappings)} reference mapping(s)")
                    reference_content = "\n\n## Reference Mapping Tables:\n\n"
                    for idx, ref_mapping in enumerate(reference_mappings, 1):
                        reference_content += f"### Reference Mapping {idx}:\n\n{ref_mapping}\n\n---\n\n"
                    prompt = prompt.replace("{reference_mappings}", reference_content)
                else:
                    prompt = prompt.replace("{reference_mappings}", "")
                
                # Add additional information if provided
                if additional_info:
                    self.logger.debug(f"Adding additional info: {len(additional_info)} characters")
                    prompt = prompt.replace("{additional_info}", additional_info)
                else:
                    prompt = prompt.replace("{additional_info}", "")
                
                self.logger.info(f"Successfully built mapping table prompt: {len(prompt)} characters")
                return prompt
            else:
                self.logger.warning(f"Prompt template not found at {template_path}, using fallback inline prompt")
                # Fallback inline prompt if template not found
                return self._build_inline_mapping_table_prompt(
                    resource_name, ig_name, ig_version, backend_source, 
                    input_json, extra_context, reference_mappings
                )
        except (ValidationError, PromptBuildError):
            raise
        except FileNotFoundError as e:
            error_msg = f"Template file not found: {e}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
        except PermissionError as e:
            error_msg = f"Permission denied accessing template or directory: {e}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error while building mapping table prompt: {e}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error building mapping table prompt: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise PromptBuildError(error_msg) from e
    
    def _build_inline_liquid_to_mapping_prompt(
        self,
        resource_name: str,
        ig_name: str,
        ig_version: str,
        backend_source: str,
        input_json: str,
        liquid_mapping: str
    ) -> str:
        """Fallback inline prompt for liquid-to-mapping conversion."""
        return f"""You are an expert in FHIR data integration and documentation.

**Implementation Guide (IG):** {ig_name} {ig_version}
**FHIR Resource Name:** {resource_name}
**Backend Source System:** {backend_source}

**Target FHIR Format (Expected Output Example):**

```json
{input_json}
```

**Liquid Mapping Template:**

```liquid
{liquid_mapping}
```

---

## Your Task:

Generate a comprehensive markdown documentation file that describes the mapping logic, field-level transformations, business rules, and any special considerations for this liquid mapping.

The documentation should include:

1. **Title and Context** - Resource name, source system, and IG
2. **Data Flow** - Describe input and output structures
3. **Field Mapping Table** - For each FHIR field:
   - FHIR field name (JSONPath)
   - Source field or logic
   - Transformation logic
   - Data type (source → FHIR)
   - Required/Optional
   - Cardinality (1..1, 0..1, 0..*, 1..*)
   - Notes

4. **Liquid Syntax Reference** - Document all Liquid elements used:
   - Variable assignments
   - Filters applied
   - Conditional logic
   - Loop iterations
   - Array indexing

5. **Conditional Logic Patterns** - Document conditional mappings with clear conditions
6. **Terminology Mappings** - Code/value transformations
7. **Null/Empty Handling** - How missing data is handled
8. **Source Data Structure** - Expected source data format
9. **Business Rules** - Key assumptions and logic
10. **Example Transformation** - Sample input → output

**Format your output as a markdown (.md) file.**
"""
    
    def build_liquid_mapping_generation_prompt(
        self,
        resource_name: str,
        ig_name: str,
        ig_version: str,
        backend_source: str,
        input_json: str,
        mapping_table_docs: List[str],
        additional_info: Optional[str] = None
    ) -> str:
        """
        Build a prompt for generating Liquid template FROM mapping table documentation.
        
        Args:
            resource_name: Name of the FHIR resource
            ig_name: Name of the Implementation Guide
            ig_version: Version of the Implementation Guide
            backend_source: Name of the backend source system
            input_json: Input JSON data structure (source data)
            mapping_table_docs: List of mapping table documentation contents
            additional_info: User-provided additional information/context (optional)
            
        Returns:
            Complete prompt for generating Liquid template
            
        Raises:
            ValidationError: If required inputs are invalid
            PromptBuildError: If prompt cannot be built
        """
        # Validate required inputs
        self._validate_identifier(resource_name, "resource_name")
        self._validate_identifier(ig_name, "ig_name")
        self._validate_identifier(ig_version, "ig_version")
        self._validate_identifier(backend_source, "backend_source")
        self._validate_string_input(input_json, "input_json")
        
        if not mapping_table_docs or len(mapping_table_docs) == 0:
            error_msg = "mapping_table_docs is required and cannot be empty"
            self.logger.error(error_msg)
            raise ValidationError(error_msg)
        
        self.logger.info(f"Building liquid generation prompt for {resource_name} ({ig_name} {ig_version}, {backend_source})")
        self.logger.debug(f"Input JSON length: {len(input_json)} bytes, "
                         f"mapping_table_docs: {len(mapping_table_docs)}, "
                         f"additional_info: {bool(additional_info)}")
        
        try:
            template_path = self.prompts_dir / "liquid_mapping_generation_prompt.md"
        
            if template_path.exists():
                self.logger.debug(f"Loading prompt template from: {template_path}")
                template = self._read_template(template_path)
                
                # Replace placeholders
                prompt = template.replace("{resource_name}", resource_name)
                prompt = prompt.replace("{ig_name}", ig_name)
                prompt = prompt.replace("{ig_version}", ig_version)
                prompt = prompt.replace("{backend_source}", backend_source)
                prompt = prompt.replace("{input_json}", input_json)
                
                # Add mapping table documentation
                if mapping_table_docs and len(mapping_table_docs) > 0:
                    self.logger.debug(f"Adding {len(mapping_table_docs)} mapping table document(s)")
                    mapping_content = "\n\n## Mapping Table Documentation:\n\n"
                    for idx, doc in enumerate(mapping_table_docs, 1):
                        mapping_content += f"### Mapping Table {idx}:\n\n{doc}\n\n---\n\n"
                    prompt = prompt.replace("{mapping_table_docs}", mapping_content)
                else:
                    prompt = prompt.replace("{mapping_table_docs}", "")
                
                # Add additional information if provided
                if additional_info:
                    self.logger.debug(f"Adding additional info: {len(additional_info)} characters")
                    prompt = prompt.replace("{additional_info}", additional_info)
                else:
                    prompt = prompt.replace("{additional_info}", "")
                
                self.logger.info(f"Successfully built liquid generation prompt: {len(prompt)} characters")
                return prompt
            else:
                self.logger.warning(f"Prompt template not found at {template_path}, using fallback inline prompt")
                # Fallback inline prompt if template not found
                return self._build_inline_liquid_generation_prompt(
                    resource_name, ig_name, ig_version, backend_source, input_json, mapping_table_docs
                )
        except (ValidationError, PromptBuildError):
            raise
        except FileNotFoundError as e:
            error_msg = f"Template file not found: {e}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
        except PermissionError as e:
            error_msg = f"Permission denied accessing template or directory: {e}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error while building liquid generation prompt: {e}"
            self.logger.error(error_msg)
            raise PromptBuildError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error building liquid generation prompt: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise PromptBuildError(error_msg) from e
    
    def _build_inline_liquid_generation_prompt(
        self,
        resource_name: str,
        ig_name: str,
        ig_version: str,
        backend_source: str,
        input_json: str,
        mapping_table_docs: List[str]
    ) -> str:
        """Fallback inline prompt for liquid template generation."""
        prompt = f"""You are an expert in FHIR data integration and Liquid template generation.

**Task**: Generate a Liquid template for transforming {backend_source} data to FHIR {resource_name} resource.

**Context**:
- **Source System**: {backend_source}
- **Target FHIR Resource**: {resource_name}
- **Implementation Guide**: {ig_name} {ig_version}
- **FHIR Release**: R4

**Input JSON Structure (Source Data)**:
```json
{input_json}
```
"""
        
        if mapping_table_docs:
            prompt += "\n\n**Mapping Table Documentation**:\n\n"
            for idx, doc in enumerate(mapping_table_docs, 1):
                prompt += f"### Mapping Table {idx}\n\n{doc}\n\n---\n\n"
        
        prompt += """
**Your Task**:

Generate a complete Liquid template that transforms the source data into a valid FHIR resource.

**Requirements**:
1. Use Liquid syntax (variables, filters, conditionals, loops)
2. Follow the mapping table documentation exactly
3. Implement all transformation logic and business rules
4. Handle null/empty values appropriately
5. Apply terminology mappings and code transformations
6. Ensure FHIR R4 compliance
7. Include proper cardinality and required fields
8. Add comments for complex logic

**Output Format**: 
- Pure Liquid template code
- No markdown code fences
- Include inline comments for clarity
- Follow best practices for Liquid templates

Generate the Liquid template now.
"""
        
        return prompt
    
    def _build_inline_mapping_table_prompt(
        self,
        resource_name: str,
        ig_name: str,
        ig_version: str,
        backend_source: str,
        input_json: str,
        extra_context: Optional[str],
        reference_mappings: Optional[List[str]]
    ) -> str:
        """Fallback inline prompt for mapping table generation."""
        prompt = f"""You are an expert in FHIR data integration and mapping documentation.

**Task**: Generate a comprehensive mapping table documentation for transforming {backend_source} data to FHIR {resource_name} resource.

**Context**:
- **Source System**: {backend_source}
- **Target FHIR Resource**: {resource_name}
- **Implementation Guide**: {ig_name} {ig_version}
- **FHIR Release**: R4

**Input JSON Structure (Source Data)**:
```json
{input_json}
```
"""
        
        if extra_context:
            prompt += f"\n\n**Additional Context**:\n{extra_context}\n"
        
        if reference_mappings:
            prompt += "\n\n**Reference Mapping Tables**:\n\n"
            for idx, ref_mapping in enumerate(reference_mappings, 1):
                prompt += f"### Reference {idx}\n\n{ref_mapping}\n\n---\n\n"
        
        prompt += """
**Your Task**:

Generate a complete mapping table documentation that includes:

1. **Overview Section**
   - Resource name and source system
   - Implementation Guide and version
   - Purpose and scope

2. **Field Mapping Table**
   Create a detailed table with columns:
   - FHIR Attribute (JSONPath notation)
   - Source Field
   - Transformation Logic
   - Data Type (source → FHIR)
   - Required/Optional
   - Cardinality
   - Notes/Comments

3. **Terminology Mappings**
   - Code system mappings
   - Value set bindings
   - Code transformations

4. **Business Rules**
   - Conditional logic
   - Default values
   - Validation rules
   - Data quality checks

5. **Null/Empty Handling**
   - How missing data is processed
   - Default behaviors
   - Required field handling

6. **Example Transformation**
   - Sample source data
   - Corresponding FHIR output

7. **Dependencies and Assumptions**
   - Required source fields
   - Data quality assumptions
   - External dependencies

**Output Format**: 
- Use markdown format with proper headers
- Use tables for field mappings
- Include code blocks for examples
- Be detailed and comprehensive
- Follow FHIR R4 and {ig_name} {ig_version} standards

Generate the mapping table documentation now.
"""
        
        return prompt
