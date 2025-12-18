"""
Service to manage extra context for FHIR resources.
Uses a simple JSON file as lightweight database for MVP.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever

from exceptions import ContextDBError, ValidationError
from utils.validators import validate_identifier, validate_required_string


class ContextDbService:
    """Stores and retrieves extra context per FHIR resource type."""
    
    def __init__(self, secret_retriever: Optional[ISecretRetriever] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize the context database service.
        
        Args:
            secret_retriever: Optional ISecretRetriever for future DB credentials
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.secret_retriever = secret_retriever
        
        # Default to Dataset within liquid_mapper use case
        current_file = Path(__file__).resolve()
        use_case_root = current_file.parent.parent
        self.db_path = use_case_root / "Dataset" / "ResourceContext" / "context.json"
        
        self.logger.info(f"Initialized ContextDbService with database path: {self.db_path}")
        
        try:
            # Ensure directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Initialize empty DB if doesn't exist
            if not self.db_path.exists():
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=2)
                self.logger.info(f"Initialized new context database file: {self.db_path}")
        except PermissionError as e:
            error_msg = f"Permission denied initializing context database at {self.db_path}: {e}"
            self.logger.error(error_msg)
            raise ContextDBError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error initializing context database at {self.db_path}: {e}"
            self.logger.error(error_msg)
            raise ContextDBError(error_msg) from e
    
    def _validate_resource_name(self, resource_name: str) -> None:
        """Validate a resource name using shared validation logic."""
        try:
            validate_required_string(resource_name, "Resource name")
            validate_identifier(resource_name, "resource name")
        except ValidationError as e:
            self.logger.error(str(e))
            raise
    
    def get_context(self, resource_name: str) -> Optional[str]:
        """
        Get extra context for a FHIR resource.
        
        Args:
            resource_name: Name of the FHIR resource (e.g., "Condition", "Patient")
            
        Returns:
            Extra context string if exists, None otherwise
            
        Raises:
            ValidationError: If resource_name is invalid
            ContextDBError: If database cannot be read
        """
        self._validate_resource_name(resource_name)
        self.logger.debug(f"Retrieving context for resource '{resource_name}'")
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            context = data.get(resource_name)
            if context:
                self.logger.info(f"Found context for resource '{resource_name}': {len(context)} characters")
            else:
                self.logger.debug(f"No context found for resource '{resource_name}'")
            return context
        except FileNotFoundError:
            self.logger.warning(f"Context database file not found: {self.db_path}")
            return None
        except json.JSONDecodeError as e:
            error_msg = f"Corrupted context database (invalid JSON): {e}"
            self.logger.error(error_msg)
            raise ContextDBError(error_msg) from e
        except PermissionError as e:
            error_msg = f"Permission denied reading context database: {e}"
            self.logger.error(error_msg)
            raise ContextDBError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error retrieving context for '{resource_name}': {e}"
            self.logger.error(error_msg, exc_info=True)
            raise ContextDBError(error_msg) from e
    
    def save_context(self, resource_name: str, context: str):
        """
        Save extra context for a FHIR resource.
        
        Args:
            resource_name: Name of the FHIR resource
            context: Extra context information to store
            
        Raises:
            ValidationError: If inputs are invalid
            ContextDBError: If database cannot be written
        """
        self._validate_resource_name(resource_name)
        
        if context is None:
            error_msg = "Context cannot be None. Use delete_context() to remove context."
            self.logger.error(error_msg)
            raise ValidationError(error_msg)
        
        self.logger.info(f"Saving context for resource '{resource_name}': {len(context)} characters")
        
        try:
            data = {}
            if self.db_path.exists():
                try:
                    with open(self.db_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Existing context file corrupted, starting fresh: {e}")
                    data = {}
            
            data[resource_name] = context
            
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Successfully saved context for resource '{resource_name}'")
        except json.JSONDecodeError as e:
            error_msg = f"Corrupted context database (invalid JSON), starting fresh: {e}"
            self.logger.warning(error_msg)
            # Attempt recovery by creating fresh database
            try:
                data = {resource_name: context}
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Recovered context database and saved context for '{resource_name}'")
            except Exception as recovery_error:
                error_msg = f"Failed to recover context database: {recovery_error}"
                self.logger.error(error_msg)
                raise ContextDBError(error_msg) from recovery_error
        except PermissionError as e:
            error_msg = f"Permission denied writing context for '{resource_name}': {e}"
            self.logger.error(error_msg)
            raise ContextDBError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error saving context for '{resource_name}': {e}"
            self.logger.error(error_msg)
            raise ContextDBError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error saving context for '{resource_name}': {e}"
            self.logger.error(error_msg, exc_info=True)
            raise ContextDBError(error_msg) from e
    
    def delete_context(self, resource_name: str) -> bool:
        """
        Delete extra context for a FHIR resource.
        
        Args:
            resource_name: Name of the FHIR resource
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            ValidationError: If resource_name is invalid
            ContextDBError: If database cannot be updated
        """
        self._validate_resource_name(resource_name)
        self.logger.info(f"Attempting to delete context for resource '{resource_name}'")
        
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if resource_name in data:
                del data[resource_name]
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Successfully deleted context for resource '{resource_name}'")
                return True
            else:
                self.logger.warning(f"No context found to delete for resource '{resource_name}'")
                return False
        except FileNotFoundError:
            self.logger.warning(f"Database file not found, cannot delete context for '{resource_name}'")
            return False
        except json.JSONDecodeError as e:
            error_msg = f"Corrupted context database (invalid JSON): {e}"
            self.logger.error(error_msg)
            raise ContextDBError(error_msg) from e
        except PermissionError as e:
            error_msg = f"Permission denied deleting context for '{resource_name}': {e}"
            self.logger.error(error_msg)
            raise ContextDBError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error deleting context for '{resource_name}': {e}"
            self.logger.error(error_msg)
            raise ContextDBError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error deleting context for '{resource_name}': {e}"
            self.logger.error(error_msg, exc_info=True)
            raise ContextDBError(error_msg) from e
    
    def list_all_contexts(self) -> dict:
        """
        List all stored contexts.
        
        Returns:
            Dictionary of resource_name -> context
        """
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
