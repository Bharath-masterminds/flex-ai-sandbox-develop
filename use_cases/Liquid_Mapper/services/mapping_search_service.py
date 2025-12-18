"""
Service to search and retrieve mapping table files from the Dataset/MappingTable directory.
Implements cascading search logic for finding relevant reference mappings.
"""
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from exceptions import MappingNotFoundError, ValidationError
from utils.validators import validate_identifier, validate_required_string


class MappingSearchService:
    """Handles searching and retrieving mapping table markdown files."""
    
    def __init__(self, base_path: Optional[Path] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize the mapping table search service.
        
        Args:
            base_path: Base path to the MappingTable directory. 
                      If None, uses use_cases/liquid_mapper/Dataset/MappingTable
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        
        if base_path is None:
            # Default to Dataset within liquid_mapper use case
            current_file = Path(__file__).resolve()
            use_case_root = current_file.parent.parent
            self.base_path = use_case_root / "Dataset" / "MappingTable"
            self.logger.info(f"Initialized MappingSearchService with default base_path: {self.base_path}")
        else:
            self.base_path = Path(base_path)
            self.logger.info(f"Initialized MappingSearchService with custom base_path: {self.base_path}")
        
        # Validate that base path exists
        if not self.base_path.exists():
            error_msg = f"Base path does not exist: {self.base_path}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        if not self.base_path.is_dir():
            error_msg = f"Base path is not a directory: {self.base_path}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.generated_path = self.base_path / "GeneratedMappingTable"
    
    def _validate_identifier(self, identifier: str, field_name: str) -> None:
        """Validate an identifier using shared validation logic."""
        try:
            validate_identifier(identifier, field_name)
        except ValidationError as e:
            self.logger.error(str(e))
            raise
    
    def search_mapping_tables_cascade(
        self, 
        resource_name: str, 
        ig_name: str = "", 
        backend_source: str = ""
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """
        Search for mapping table files with cascading logic.
        Searches both resource-specific folders and GeneratedMappingTable folder.
        
        Cascade levels:
        1. Exact: Resource + IG + Backend Source
        2. Resource + IG
        3. Resource + Backend Source
        4. Resource only (all mappings)
        
        Args:
            resource_name: Name of the FHIR resource (required)
            ig_name: Name of the Implementation Guide (optional)
            backend_source: Name of the backend source system (optional)
            
        Returns:
            Tuple of (search_level, list of (file_path, file_name) tuples)
            search_level: "exact", "resource_ig", "resource_backend", "resource_only", or "none"
            
        Raises:
            ValidationError: If resource_name is empty or contains invalid characters
            MappingNotFoundError: If no mappings found for the resource
        """
        # Validate inputs
        if not resource_name or not resource_name.strip():
            error_msg = "Resource name is required and cannot be empty"
            self.logger.error(error_msg)
            raise ValidationError(error_msg)
        
        self._validate_identifier(resource_name, "resource_name")
        self._validate_identifier(ig_name, "ig_name")
        self._validate_identifier(backend_source, "backend_source")
        
        self.logger.info(f"Starting cascading search for resource='{resource_name}', ig='{ig_name}', backend='{backend_source}'")
        
        resource_folder = self.base_path / resource_name
        
        # Get all .md files from the resource folder
        all_md_files = []
        if resource_folder.exists() and resource_folder.is_dir():
            all_md_files = [f for f in resource_folder.glob("*.md") if f.is_file()]
            self.logger.debug(f"Found {len(all_md_files)} files in resource folder: {resource_folder}")
        else:
            self.logger.debug(f"Resource folder does not exist: {resource_folder}")
        
        # Get all .md files from GeneratedMappingTable that match the resource
        all_generated_files = []
        if self.generated_path.exists() and self.generated_path.is_dir():
            for file_path in self.generated_path.glob("*.md"):
                if file_path.is_file():
                    file_name_lower = file_path.stem.lower()
                    if file_name_lower.startswith(resource_name.lower()):
                        all_generated_files.append(file_path)
            self.logger.debug(f"Found {len(all_generated_files)} matching files in GeneratedMappingTable")
        else:
            self.logger.debug(f"Generated folder does not exist: {self.generated_path}")
        
        # Combine all files
        all_files = all_md_files + all_generated_files
        
        if not all_files:
            error_msg = f"No mapping tables found for resource '{resource_name}'"
            self.logger.warning(error_msg)
            raise MappingNotFoundError(error_msg)
        
        self.logger.info(f"Total files found for '{resource_name}': {len(all_files)}")
        
        # Step 1: Try exact match (Resource + IG + Backend Source)
        if ig_name and backend_source:
            exact_matches = []
            for file_path in all_files:
                file_stem_lower = file_path.stem.lower()
                if (ig_name.lower() in file_stem_lower and 
                    backend_source.lower() in file_stem_lower):
                    exact_matches.append((str(file_path), file_path.name))
            
            if exact_matches:
                self.logger.info(f"Found {len(exact_matches)} exact matches (resource+ig+backend)")
                return "exact", exact_matches
        
        # Step 2: Try Resource + IG match
        if ig_name:
            ig_matches = []
            for file_path in all_files:
                file_stem_lower = file_path.stem.lower()
                if ig_name.lower() in file_stem_lower:
                    ig_matches.append((str(file_path), file_path.name))
            
            if ig_matches:
                self.logger.info(f"Found {len(ig_matches)} resource+IG matches")
                return "resource_ig", ig_matches
        
        # Step 3: Try Resource + Backend Source match
        if backend_source:
            backend_matches = []
            for file_path in all_files:
                file_stem_lower = file_path.stem.lower()
                if backend_source.lower() in file_stem_lower:
                    backend_matches.append((str(file_path), file_path.name))
            
            if backend_matches:
                self.logger.info(f"Found {len(backend_matches)} resource+backend matches")
                return "resource_backend", backend_matches
        
        # Step 4: Return all files for the resource
        all_resource_files = [(str(f), f.name) for f in all_files]
        self.logger.info(f"Returning all {len(all_resource_files)} files for resource '{resource_name}'")
        return "resource_only", all_resource_files
    
    def read_mapping_table(self, file_path: str) -> str:
        """
        Read the content of a mapping table file.
        
        Args:
            file_path: Path to the mapping table file
            
        Returns:
            Content of the mapping table file
            
        Raises:
            ValidationError: If file_path is empty or invalid
            FileNotFoundError: If file does not exist
            IOError: If file cannot be read
            ValueError: If file is empty
        """
        # Validate input
        if not file_path or not file_path.strip():
            error_msg = "File path is required and cannot be empty"
            self.logger.error(error_msg)
            raise ValidationError(error_msg)
        
        self.logger.debug(f"Reading mapping table file: {file_path}")
        
        try:
            path_obj = Path(file_path)
            
            # Check if file exists
            if not path_obj.exists():
                error_msg = f"Mapping table file not found: {file_path}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # Check if it's a file (not a directory)
            if not path_obj.is_file():
                error_msg = f"Path is not a file: {file_path}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate content is not empty
            if not content or not content.strip():
                error_msg = f"Mapping table file is empty: {file_path}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            self.logger.info(f"Successfully read mapping table: {file_path} ({len(content)} bytes)")
            return content
            
        except FileNotFoundError:
            raise
        except ValueError:
            raise
        except IOError as e:
            error_msg = f"I/O error reading mapping table file {file_path}: {e}"
            self.logger.error(error_msg)
            raise IOError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error reading mapping table file {file_path}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise IOError(error_msg) from e
