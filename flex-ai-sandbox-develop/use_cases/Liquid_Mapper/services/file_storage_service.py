"""
Service to save generated mapping tables and liquid templates.
Handles file naming, collision detection, and directory management.
Paths are configurable via LiquidMapperIocConfig.
"""
import logging
from pathlib import Path
from typing import Optional

from exceptions import FileStorageError, ValidationError, PathTraversalError
from utils.validators import validate_filename_component, sanitize_filename


class FileStorageService:
    """Handles saving generated mapping tables and liquid templates."""
    
    def __init__(
        self, 
        mapping_table_path: Optional[Path] = None,
        liquid_template_path: Optional[Path] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the file storage service.
        
        Args:
            mapping_table_path: Full absolute path to mapping table directory.
                      If None, uses use_cases/liquid_mapper/Dataset/MappingTable/GeneratedMappingTable
            liquid_template_path: Full absolute path to liquid template directory.
                      If None, uses use_cases/liquid_mapper/Dataset/LiquidMapping/Generated
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        
        if mapping_table_path is None:
            # Default to use_cases/liquid_mapper/Dataset/MappingTable/GeneratedMappingTable
            current_file = Path(__file__).resolve()
            use_case_root = current_file.parent.parent
            self.mapping_table_path = use_case_root / "Dataset" / "MappingTable" / "GeneratedMappingTable"
            self.logger.info(f"Initialized FileStorageService with default mapping_table_path: {self.mapping_table_path}")
        else:
            self.mapping_table_path = Path(mapping_table_path)
            self.logger.info(f"Initialized FileStorageService with custom mapping_table_path: {self.mapping_table_path}")
        
        if liquid_template_path is None:
            # Default to use_cases/liquid_mapper/Dataset/LiquidMapping/Generated
            current_file = Path(__file__).resolve()
            use_case_root = current_file.parent.parent
            self.liquid_template_path = use_case_root / "Dataset" / "LiquidMapping" / "Generated"
            self.logger.info(f"Default liquid_template_path: {self.liquid_template_path}")
        else:
            self.liquid_template_path = Path(liquid_template_path)
            self.logger.info(f"Custom liquid_template_path: {self.liquid_template_path}")
    
    def _validate_filename_component(self, component: str, field_name: str) -> None:
        """Validate a filename component using shared validation logic."""
        try:
            validate_filename_component(component, field_name)
        except (ValidationError, PathTraversalError) as e:
            self.logger.error(str(e))
            raise
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename using shared utility."""
        return sanitize_filename(filename)
    
    def _ensure_directory_exists(self, directory: Path) -> None:
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            directory: Path to the directory
            
        Raises:
            FileStorageError: If directory cannot be created
        """
        try:
            directory.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Ensured directory exists: {directory}")
        except PermissionError as e:
            error_msg = f"Permission denied creating directory {directory}: {e}"
            self.logger.error(error_msg)
            raise FileStorageError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error creating directory {directory}: {e}"
            self.logger.error(error_msg)
            raise FileStorageError(error_msg) from e
    
    @staticmethod
    def _clean_markdown_content(content: str) -> str:
        """
        Remove markdown code fences from LLM-generated content.
        
        Args:
            content: The raw content from LLM
            
        Returns:
            Cleaned markdown content without code fences
        """
        # Remove opening markdown code fence (```markdown or ```)
        if content.startswith('```markdown'):
            content = content[len('```markdown'):].lstrip('\n')
        elif content.startswith('```'):
            content = content[3:].lstrip('\n')
        
        # Remove closing code fence (```)
        if content.rstrip().endswith('```'):
            content = content.rstrip()[:-3].rstrip()
        
        return content
    
    @staticmethod
    def _clean_liquid_content(content: str) -> str:
        """
        Remove code fences from LLM-generated liquid template content.
        
        Args:
            content: The raw content from LLM
            
        Returns:
            Cleaned liquid content without code fences
        """
        lines = content.strip().split('\n')
        
        # Check if first line is a code fence
        if lines and lines[0].strip().startswith('```'):
            lines = lines[1:]
        
        # Check if last line is a code fence
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        
        return '\n'.join(lines)
    
    def save_mapping_table(
        self,
        content: str,
        resource_name: str,
        ig_version: str,
        backend_source: str
    ) -> str:
        """
        Save generated mapping table to a file.
        
        Filename format: {ResourceName}.{IG_Version}.{BackendSource}.MappingTable.md
        Example: Condition.USCore_6.1.0.eCW.MappingTable.md
        
        Args:
            content: The generated mapping table content
            resource_name: Name of the FHIR resource (will be capitalized)
            ig_version: Implementation Guide with version (e.g., "USCore_6.1.0")
            backend_source: Name of the backend source system
            
        Returns:
            Path to the saved file
            
        Raises:
            ValidationError: If inputs are invalid or contain forbidden characters
            PathTraversalError: If path traversal attempt detected
            FileStorageError: If file cannot be saved
        """
        self.logger.info(f"Saving mapping table for resource='{resource_name}', ig='{ig_version}', backend='{backend_source}'")
        
        try:
            # Validate inputs
            if not content or not content.strip():
                error_msg = "Content is required and cannot be empty"
                self.logger.error(error_msg)
                raise ValidationError(error_msg)
            
            self._validate_filename_component(resource_name, "resource_name")
            self._validate_filename_component(ig_version, "ig_version")
            self._validate_filename_component(backend_source, "backend_source")
            
            # Ensure directory exists
            self._ensure_directory_exists(self.mapping_table_path)
            
            # Capitalize resource name
            capitalized_resource = resource_name.capitalize()
            
            # Create base filename
            base_filename = f"{capitalized_resource}.{ig_version}.{backend_source}.MappingTable.md"
            file_path = self.mapping_table_path / base_filename
            
            # Handle collision - append _X suffix if needed
            if file_path.exists():
                self.logger.warning(f"File already exists, finding alternative name: {base_filename}")
                counter = 1
                filename_without_ext = f"{capitalized_resource}.{ig_version}.{backend_source}.MappingTable"
                while True:
                    new_filename = f"{filename_without_ext}_{counter}.md"
                    file_path = self.mapping_table_path / new_filename
                    if not file_path.exists():
                        self.logger.info(f"Using alternative filename: {new_filename}")
                        break
                    counter += 1
            
            # Clean and save content
            cleaned_content = self._clean_markdown_content(content)
            self.logger.debug(f"Cleaned content: {len(content)} -> {len(cleaned_content)} bytes")
            
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
            except PermissionError as e:
                error_msg = f"Permission denied writing to {file_path}: {e}"
                self.logger.error(error_msg)
                raise FileStorageError(error_msg) from e
            except OSError as e:
                error_msg = f"OS error writing mapping table to {file_path}: {e}"
                self.logger.error(error_msg)
                raise FileStorageError(error_msg) from e
            
            self.logger.info(f"Successfully saved mapping table to: {file_path}")
            return str(file_path)
            
        except (ValidationError, PathTraversalError, FileStorageError):
            raise
        except Exception as e:
            error_msg = f"Unexpected error saving mapping table: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise FileStorageError(error_msg) from e
    
    def save_liquid_template(
        self,
        content: str,
        resource_name: str,
        ig_version: str,
        backend_source: str
    ) -> str:
        """
        Save generated liquid template to a file.
        
        Filename format: {ResourceName}.{IG_Version}.{BackendSource}.liquid
        Example: Condition.USCore_6.1.0.eCW.liquid
        
        Args:
            content: The generated liquid template content
            resource_name: Name of the FHIR resource (will be capitalized)
            ig_version: Implementation Guide with version
            backend_source: Name of the backend source system
            
        Returns:
            Path to the saved file
            
        Raises:
            ValidationError: If inputs are invalid or contain forbidden characters
            PathTraversalError: If path traversal attempt detected
            FileStorageError: If file cannot be saved
        """
        self.logger.info(f"Saving liquid template for resource='{resource_name}', ig='{ig_version}', backend='{backend_source}'")
        
        try:
            # Validate inputs
            if not content or not content.strip():
                error_msg = "Content is required and cannot be empty"
                self.logger.error(error_msg)
                raise ValidationError(error_msg)
            
            self._validate_filename_component(resource_name, "resource_name")
            self._validate_filename_component(ig_version, "ig_version")
            self._validate_filename_component(backend_source, "backend_source")
            
            # Ensure directory exists
            self._ensure_directory_exists(self.liquid_template_path)
            
            # Capitalize resource name
            capitalized_resource = resource_name.capitalize()
            
            # Create base filename
            base_filename = f"{capitalized_resource}.{ig_version}.{backend_source}.liquid"
            file_path = self.liquid_template_path / base_filename
            
            # Handle collision - append _X suffix if needed
            if file_path.exists():
                self.logger.warning(f"File already exists, finding alternative name: {base_filename}")
                counter = 1
                filename_without_ext = f"{capitalized_resource}.{ig_version}.{backend_source}"
                while True:
                    new_filename = f"{filename_without_ext}_{counter}.liquid"
                    file_path = self.liquid_template_path / new_filename
                    if not file_path.exists():
                        self.logger.info(f"Using alternative filename: {new_filename}")
                        break
                    counter += 1
            
            # Clean and save content
            cleaned_content = self._clean_liquid_content(content)
            self.logger.debug(f"Cleaned content: {len(content)} -> {len(cleaned_content)} bytes")
            
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
            except PermissionError as e:
                error_msg = f"Permission denied writing to {file_path}: {e}"
                self.logger.error(error_msg)
                raise FileStorageError(error_msg) from e
            except OSError as e:
                error_msg = f"OS error writing liquid template to {file_path}: {e}"
                self.logger.error(error_msg)
                raise FileStorageError(error_msg) from e
            
            self.logger.info(f"Successfully saved liquid template to: {file_path}")
            return str(file_path)
            
        except (ValidationError, PathTraversalError, FileStorageError):
            raise
        except Exception as e:
            error_msg = f"Unexpected error saving liquid template: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise FileStorageError(error_msg) from e
