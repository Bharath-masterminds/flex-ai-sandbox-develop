"""
IoC Configuration for Liquid Mapper use case.
Reads dataset paths from config map retriever.
"""
from pathlib import Path
from typing import Optional

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever


class LiquidMapperIocConfig:
    """Configuration for Liquid Mapper IoC container - manages dataset paths."""
    
    def __init__(self, config_map_retriever: IConfigMapRetriever):
        """
        Initialize configuration with a config map retriever.
        
        Args:
            config_map_retriever: IConfigMapRetriever for reading configuration values
        """
        self.config_map_retriever = config_map_retriever
        self._dataset_base_path: Optional[str] = None
        self._mapping_table_subpath: Optional[str] = None
        self._liquid_template_subpath: Optional[str] = None
        self._resource_context_subpath: Optional[str] = None
    
    def _get_config_value(self, key: str, default: str) -> str:
        """
        Get a configuration value from config map retriever with fallback to default.
        
        Args:
            key: Configuration key name
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        try:
            # LocalFileConfigMapRetriever is async, but we need sync access during initialization
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            value = loop.run_until_complete(
                self.config_map_retriever.retrieve_optional_config_map_value(key)
            )
            return value if value is not None else default
        except Exception:
            # If retrieval fails, return default
            return default
    
    @property
    def dataset_base_path(self) -> str:
        """Get dataset base path from config map."""
        if self._dataset_base_path is None:
            self._dataset_base_path = self._get_config_value("LIQUID_MAPPER_DATASET_PATH", "Dataset")
        return self._dataset_base_path
    
    @property
    def mapping_table_subpath(self) -> str:
        """Get mapping table subpath from config map."""
        if self._mapping_table_subpath is None:
            self._mapping_table_subpath = self._get_config_value("MAPPING_TABLE_SUBPATH", "MappingTable/GeneratedMappingTable")
        return self._mapping_table_subpath
    
    @property
    def liquid_template_subpath(self) -> str:
        """Get liquid template subpath from config map."""
        if self._liquid_template_subpath is None:
            self._liquid_template_subpath = self._get_config_value("LIQUID_TEMPLATE_SUBPATH", "LiquidMapping/Generated")
        return self._liquid_template_subpath
    
    @property
    def resource_context_subpath(self) -> str:
        """Get resource context subpath from config map."""
        if self._resource_context_subpath is None:
            self._resource_context_subpath = self._get_config_value("RESOURCE_CONTEXT_SUBPATH", "ResourceContext")
        return self._resource_context_subpath
    
    @staticmethod
    def get_use_case_root() -> Path:
        """Get the absolute path to the liquid_mapper use case root directory."""
        # This config file is in use_cases/liquid_mapper/ioc/
        config_file_path = Path(__file__).resolve()
        use_case_root = config_file_path.parent.parent  # Go up two levels: ioc -> liquid_mapper
        return use_case_root
    
    def get_full_mapping_table_path(self) -> Path:
        """Get the full absolute path to the mapping table directory."""
        return self.get_use_case_root() / self.dataset_base_path / self.mapping_table_subpath
    
    def get_full_liquid_template_path(self) -> Path:
        """Get the full absolute path to the liquid template directory."""
        return self.get_use_case_root() / self.dataset_base_path / self.liquid_template_subpath
    
    def get_full_resource_context_path(self) -> Path:
        """Get the full absolute path to the resource context directory."""
        return self.get_use_case_root() / self.dataset_base_path / self.resource_context_subpath

