"""
Streamlit UI for Liquid Mapper - FHIR Mapping Table and Liquid Template Generator

Step 0: Generate Mapping Table Documentation (with optional reference mappings and liquid template)
Step 1: Generate Liquid Template (from existing mapping tables)
"""
import sys
from pathlib import Path

# Ensure workspace root is in sys.path for local imports
workspace_root = Path(__file__).parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

import asyncio
import json
import logging
from typing import Any

import streamlit as st
from dotenv import load_dotenv

# Load environment variables BEFORE importing IoC components
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('liquid_mapper.log')
    ]
)
logger = logging.getLogger(__name__)

# Add use case directory to path for relative imports
use_case_dir = Path(__file__).parent
if str(use_case_dir) not in sys.path:
    sys.path.insert(0, str(use_case_dir))

from ioc.liquid_mapper_composition_root import LiquidMapperCompositionRoot
from exceptions import (
    LiquidMapperError,
    MappingNotFoundError,
    FileStorageError,
    ContextDBError,
    PromptBuildError,
    ValidationError,
    PathTraversalError
)


# Page configuration
st.set_page_config(
    page_title="Liquid Mapper - FHIR Mapping Tool",
    page_icon="💧",
    layout="wide"
)


@st.cache_resource
def get_ioc_container():
    """
    Create and cache the IoC container to ensure singletons work across Streamlit reruns.
    This prevents the container from being recreated on every Streamlit interaction.
    """
    logger.info("Initializing IoC container for Liquid Mapper")
    try:
        container = LiquidMapperCompositionRoot()
        logger.info("IoC container initialized successfully")
        return container
    except Exception as e:
        logger.error(f"Failed to initialize IoC container: {e}")
        raise


def validate_json(json_string: str) -> tuple[bool, str | None]:
    """Validate if the input is valid JSON."""
    try:
        json.loads(json_string)
        return True, None
    except json.JSONDecodeError as e:
        return False, str(e)


async def generate_content(
    prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 16000
) -> str:
    """
    Generate content using Azure OpenAI.
    
    Args:
        prompt: Complete prompt for generation
        temperature: Sampling temperature (lower = more deterministic)
        max_tokens: Maximum tokens in response
        
    Returns:
        Generated content
    """
    logger.info(f"Starting content generation (temperature={temperature}, max_tokens={max_tokens})")
    logger.debug(f"Prompt length: {len(prompt)} characters")
    
    try:
        container = get_ioc_container()
        llm_creator = container.get_llm_creator()
        
        # Create LLM instance
        logger.debug("Creating LLM instance")
        llm = await llm_creator.create_llm()
        
        # Generate response
        logger.info("Invoking LLM for content generation")
        response = await llm.ainvoke([
            {"role": "system", "content": "You are an expert in FHIR data integration, HL7 standards, and healthcare data mapping. You create comprehensive, accurate documentation."},
            {"role": "user", "content": prompt}
        ])
        
        logger.info(f"Content generated successfully: {len(response.content)} characters")
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating content: {e}", exc_info=True)
        raise


def step_0_generate_mapping_table():
    """Step 0: Generate Mapping Table Documentation (with optional reference mappings)"""
    logger.info("Entering Step 0: Generate Mapping Table Documentation")
    st.header("📋 Step 0: Generate Mapping Table Documentation")
    st.markdown("Generate comprehensive mapping table documentation from input JSON, optionally with Liquid template and reference mappings.")
    
    # Get services at function level (outside conditionals) so they're available for save button
    container = get_ioc_container()
    mapping_search_service = container.get_mapping_search_service()
    context_db_service = container.get_context_db_service()
    file_storage_service = container.get_file_storage_service()
    
    # Step 1: Input fields for search
    col1, col2, col3 = st.columns(3)
    
    with col1:
        resource_name = st.text_input(
            "FHIR Resource Name *",
            placeholder="e.g., Condition, Patient, Observation",
            help="Enter the name of the FHIR resource (Required)",
            key="step0_resource_name"
        )
    
    with col2:
        ig_version = st.text_input(
            "IG with Version",
            placeholder="e.g., USCore_6.1.0, CARIN_2.0.0",
            help="Optional: Search for mappings with specific IG version",
            key="step0_ig_version"
        )
    
    with col3:
        backend_source = st.text_input(
            "Backend Source System",
            placeholder="e.g., eCW, Unity, HCP",
            help="Optional: Search for mappings from specific backend",
            key="step0_backend_source"
        )
    
    # Search button
    if st.button("🔍 Search for Reference Mapping Tables", use_container_width=True, key="step0_search"):
        # Clear previous generated content to refresh screen
        if 'step0_generated_content' in st.session_state:
            del st.session_state['step0_generated_content']
        if 'step0_save_resource_name' in st.session_state:
            del st.session_state['step0_save_resource_name']
        if 'step0_save_ig_version' in st.session_state:
            del st.session_state['step0_save_ig_version']
        if 'step0_save_backend_source' in st.session_state:
            del st.session_state['step0_save_backend_source']
        if 'step0_selected_files' in st.session_state:
            del st.session_state['step0_selected_files']
        
        if not resource_name:
            st.error("❌ Please enter a Resource Name to search")
        else:
            try:
                with st.spinner("🔎 Searching for matching mapping tables..."):
                    search_level, found_files = mapping_search_service.search_mapping_tables_cascade(
                        resource_name=resource_name,
                        ig_name=ig_version if ig_version else "",
                        backend_source=backend_source if backend_source else ""
                    )
                
                # Store search results and parameters in session state
                st.session_state['step0_search_level'] = search_level
                st.session_state['step0_found_files'] = found_files
                st.session_state['step0_search_params'] = {
                    'resource_name': resource_name,
                    'ig_version': ig_version,
                    'backend_source': backend_source
                }
                
                if found_files:
                    st.success(f"✅ Found {len(found_files)} mapping table(s) at level: **{search_level}**")
                else:
                    st.info("ℹ️ No existing mapping tables found. You can still generate a new one below.")
            
            except ValidationError as e:
                st.error(f"❌ Validation Error: {str(e)}")
                st.info("💡 **Tip**: Resource name should contain only alphanumeric characters, dots, hyphens, and underscores")
            except MappingNotFoundError as e:
                st.info(f"ℹ️ {str(e)}")
                st.info("💡 **Tip**: You can still generate a new mapping table below")
            except Exception as e:
                st.error(f"❌ Search Error: {str(e)}")
                logger.error(f"Error during mapping search: {e}", exc_info=True)
    
    # Display search results if available
    if 'step0_found_files' in st.session_state and st.session_state['step0_found_files']:
        st.markdown("---")
        st.subheader("📚 Found Mapping Tables")
        st.caption(f"Search Level: {st.session_state['step0_search_level']}")
        
        found_files = st.session_state['step0_found_files']
        
        # Multi-select for choosing reference mappings
        st.markdown("**Select mapping tables to use as reference:**")
        selected_files = []
        
        for file_path, file_name in found_files:
            # Read file content for preview
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            is_selected = st.checkbox(
                f"📄 {file_name}",
                key=f"step0_select_{file_name}",
                value=False
            )
            
            if is_selected:
                selected_files.append((file_path, file_name, content))
                with st.expander(f"👁️ Preview: {file_name}"):
                    st.markdown(content[:500] + "..." if len(content) > 500 else content)
        
        st.session_state['step0_selected_files'] = selected_files
        
        if selected_files:
            st.info(f"✅ {len(selected_files)} mapping table(s) selected as reference")
    
    # Generation section
    st.markdown("---")
    st.subheader("🚀 Generate Mapping Table")
    
    with st.form("step0_generate_form"):
        # Use search params if available, otherwise ask for them
        if 'step0_search_params' in st.session_state:
            params = st.session_state['step0_search_params']
            final_resource_name = params['resource_name']
            st.info(f"**Resource:** {final_resource_name}")
        else:
            final_resource_name = st.text_input("Resource Name *", key="step0_final_resource")
        
        col_ig, col_backend = st.columns(2)
        with col_ig:
            if 'step0_search_params' in st.session_state and st.session_state['step0_search_params']['ig_version']:
                final_ig_version = st.text_input(
                    "Final IG with Version *",
                    value=st.session_state['step0_search_params']['ig_version'],
                    key="step0_final_ig"
                )
            else:
                final_ig_version = st.text_input(
                    "IG with Version *",
                    placeholder="e.g., USCore_6.1.0",
                    key="step0_final_ig"
                )
        
        with col_backend:
            if 'step0_search_params' in st.session_state and st.session_state['step0_search_params']['backend_source']:
                final_backend_source = st.text_input(
                    "Final Backend Source *",
                    value=st.session_state['step0_search_params']['backend_source'],
                    key="step0_final_backend"
                )
            else:
                final_backend_source = st.text_input(
                    "Backend Source System *",
                    placeholder="e.g., eCW, Unity",
                    key="step0_final_backend"
                )
        
        additional_info = st.text_area(
            "Additional Information (Optional)",
            height=100,
            placeholder="Provide any additional context, business rules, or special requirements for this mapping...",
            help="Optional: Any extra context that should be considered when generating the mapping table",
            key="step0_additional_info"
        )
        
        input_json = st.text_area(
            "Input JSON (Backend Source Data) *",
            height=200,
            placeholder='{"diagnosis_code": "E11.9", "diagnosis_date": "2024-01-15"}',
            help="Paste the backend source data structure",
            key="step0_input_json"
        )
        
        liquid_mapping = st.text_area(
            "Liquid Mapping Template (Optional)",
            height=250,
            placeholder='Leave empty if generating from scratch, or paste existing Liquid template',
            help="Optional: Include existing Liquid template to document",
            key="step0_liquid_mapping"
        )
        
        with st.expander("⚙️ Advanced Options"):
            col_temp, col_tokens = st.columns(2)
            with col_temp:
                temperature = st.slider(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.1,
                    step=0.1,
                    help="Controls randomness",
                    key="step0_temperature"
                )
            with col_tokens:
                max_tokens = st.number_input(
                    "Max Tokens",
                    min_value=1000,
                    max_value=32000,
                    value=16000,
                    step=1000,
                    help="Maximum output length",
                    key="step0_max_tokens"
                )
        
        generate_button = st.form_submit_button(
            "🚀 Generate Mapping Table Documentation",
            use_container_width=True,
            type="primary"
        )
        
        if generate_button:
            # Validation
            if not final_resource_name:
                st.error("❌ Please provide Resource Name")
                st.stop()
            
            if not final_ig_version:
                st.error("❌ Please provide IG with Version")
                st.stop()
            
            if not final_backend_source:
                st.error("❌ Please provide Backend Source")
                st.stop()
            
            if not input_json:
                st.error("❌ Please enter Input JSON")
                st.stop()
            
            is_valid, error_msg = validate_json(input_json)
            if not is_valid:
                st.error(f"❌ Invalid JSON: {error_msg}")
                st.stop()
            
            try:
                # Get prompt builder from services
                import sys
                sys.path.insert(0, str(Path(__file__).parent))
                from services.prompt_builder_service import PromptBuilderService
                prompt_builder = PromptBuilderService()
                
                # Get extra context if exists
                extra_context = context_db_service.get_context(final_resource_name)
                
                if extra_context:
                    st.info(f"📋 Using extra context for **{final_resource_name}**")
                
                # Prepare reference mappings from selected files
                reference_contents = []
                if 'step0_selected_files' in st.session_state:
                    reference_contents = [content for _, _, content in st.session_state['step0_selected_files']]
                
                # Add liquid mapping to reference if provided
                if liquid_mapping and liquid_mapping.strip():
                    liquid_doc = f"## Existing Liquid Template:\n\n```liquid\n{liquid_mapping}\n```"
                    reference_contents.append(liquid_doc)
                
                # Build prompt using mapping_table_generation_prompt.md
                with st.spinner("📝 Building prompt..."):
                    prompt = prompt_builder.build_mapping_table_prompt(
                        resource_name=final_resource_name,
                        ig_name=final_ig_version.split('_')[0] if '_' in final_ig_version else final_ig_version,
                        ig_version=final_ig_version,
                        backend_source=final_backend_source,
                        input_json=input_json,
                        extra_context=extra_context,
                        reference_mappings=reference_contents if reference_contents else None,
                        additional_info=additional_info if additional_info and additional_info.strip() else None
                    )
                
                with st.expander("🔍 View Generated Prompt (for debugging)"):
                    st.text(prompt)
                
                # Generate
                with st.spinner("🤖 Generating mapping table documentation..."):
                    generated_content = asyncio.run(
                        generate_content(
                            prompt=prompt,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                    )
                
                st.success("✅ Mapping table documentation generated successfully!")
                
                # Store in session state for save/download buttons
                st.session_state['step0_generated_content'] = generated_content
                st.session_state['step0_save_resource_name'] = final_resource_name
                st.session_state['step0_save_ig_version'] = final_ig_version
                st.session_state['step0_save_backend_source'] = final_backend_source
                
            except ValidationError as e:
                st.error(f"❌ Validation Error: {str(e)}")
                st.info("💡 **Tip**: Check that your inputs contain only valid characters (alphanumeric, dots, hyphens, underscores)")
            except PathTraversalError as e:
                st.error(f"🚨 Security Error: {str(e)}")
                st.warning("⚠️ Path traversal attempts are not allowed")
            except PromptBuildError as e:
                st.error(f"❌ Prompt Build Error: {str(e)}")
                st.info("💡 **Tip**: This may be due to missing or corrupted prompt templates. Check the logs for details.")
            except ContextDBError as e:
                st.error(f"❌ Context Database Error: {str(e)}")
                st.info("💡 **Tip**: There may be an issue with the context database. Try continuing without extra context.")
            except LiquidMapperError as e:
                st.error(f"❌ Liquid Mapper Error: {str(e)}")
            except Exception as e:
                st.error(f"❌ Unexpected Error: {str(e)}")
                logger.error(f"Unexpected error in step0 generation: {e}", exc_info=True)
                with st.expander("🐛 View Error Details (for debugging)"):
                    st.exception(e)
    
    # Display and save/download section - OUTSIDE the generate button block
    # This ensures it persists across Streamlit reruns when save button is clicked
    if 'step0_generated_content' in st.session_state and st.session_state['step0_generated_content']:
        # Display generated content in collapsible expander
        st.markdown("---")
        with st.expander("📄 View Generated Mapping Table Documentation", expanded=True):
            st.markdown(st.session_state['step0_generated_content'])
        
        # Save options
        st.markdown("---")
        st.subheader("💾 Save Options")
        
        col_save, col_download = st.columns(2)
        
        with col_save:
            if st.button("✅ Save to Dataset", use_container_width=True, type="primary", key="step0_save_btn"):
                try:
                    # Retrieve from session state
                    content_to_save = st.session_state.get('step0_generated_content')
                    res_name = st.session_state.get('step0_save_resource_name')
                    ig_ver = st.session_state.get('step0_save_ig_version')
                    backend = st.session_state.get('step0_save_backend_source')
                    
                    if not content_to_save:
                        st.error("❌ No content to save. Please generate mapping table first.")
                    else:
                        with st.spinner("💾 Saving mapping table..."):
                            saved_path = file_storage_service.save_mapping_table(
                                content=content_to_save,
                                resource_name=res_name,
                                ig_version=ig_ver,
                                backend_source=backend
                            )
                        st.success(f"✅ Saved to: `{saved_path}`")
                except ValidationError as e:
                    st.error(f"❌ Validation Error: {str(e)}")
                    st.info("💡 **Tip**: Check that resource name, IG version, and backend source contain only valid characters")
                except PathTraversalError as e:
                    st.error(f"🚨 Security Error: {str(e)}")
                    st.warning("⚠️ Path traversal attempts are not allowed")
                except FileStorageError as e:
                    st.error(f"❌ File Storage Error: {str(e)}")
                    st.info("💡 **Tip**: Check file permissions and disk space")
                except PermissionError as e:
                    st.error(f"❌ Permission Denied: {str(e)}")
                    st.info("💡 **Tip**: You may not have write permissions to the target directory")
                except Exception as e:
                    st.error(f"❌ Unexpected error saving file: {str(e)}")
                    logger.error(f"Error saving mapping table: {e}", exc_info=True)
                    with st.expander("🐛 View Error Details (for debugging)"):
                        st.exception(e)
        
        with col_download:
            # Download button - use session state
            content_to_download = st.session_state.get('step0_generated_content')
            res_name = st.session_state.get('step0_save_resource_name')
            ig_ver = st.session_state.get('step0_save_ig_version')
            backend = st.session_state.get('step0_save_backend_source')
            
            filename = f"{res_name.capitalize()}.{ig_ver}.{backend}.MappingTable.md"
            st.download_button(
                label="⬇️ Download Mapping Table",
                data=content_to_download,
                file_name=filename,
                mime="text/markdown",
                use_container_width=True,
                key="step0_download_btn"
            )


def step_1_generate_liquid_template():
    """Step 1: Generate Liquid Template from Mapping Tables"""
    st.header("⚡ Step 1: Generate Liquid Template")
    st.markdown("Generate Liquid template from existing mapping table documentation and input JSON.")
    
    # Get services at function level (outside conditionals) so they're available for save button
    container = get_ioc_container()
    mapping_search_service = container.get_mapping_search_service()
    file_storage_service = container.get_file_storage_service()
    
    # Step 1: Search for mapping tables
    col1, col2, col3 = st.columns(3)
    
    with col1:
        resource_name = st.text_input(
            "FHIR Resource Name *",
            placeholder="e.g., Condition, Patient, Observation",
            help="Enter the name of the FHIR resource (Required)",
            key="step1_resource_name"
        )
    
    with col2:
        ig_version = st.text_input(
            "IG with Version",
            placeholder="e.g., USCore_6.1.0, CARIN_2.0.0",
            help="Enter the IG name with version (Optional)",
            key="step1_ig_version"
        )
    
    with col3:
        backend_source = st.text_input(
            "Backend Source System",
            placeholder="e.g., eCW, Unity, HCP",
            help="Enter your source system name (Optional)",
            key="step1_backend_source"
        )
    
    # Search button
    if st.button("🔍 Search Mapping Tables", use_container_width=True, key="step1_search"):
        # Clear previous generated content to refresh screen
        if 'step1_generated_content' in st.session_state:
            del st.session_state['step1_generated_content']
        if 'step1_save_resource_name' in st.session_state:
            del st.session_state['step1_save_resource_name']
        if 'step1_save_ig_version' in st.session_state:
            del st.session_state['step1_save_ig_version']
        if 'step1_save_backend_source' in st.session_state:
            del st.session_state['step1_save_backend_source']
        if 'step1_selected_files' in st.session_state:
            del st.session_state['step1_selected_files']
        
        if not resource_name:
            st.error("❌ Please enter a Resource Name to search")
        else:
            with st.spinner("🔎 Searching for matching mapping tables..."):
                search_level, found_files = mapping_search_service.search_mapping_tables_cascade(
                    resource_name=resource_name,
                    ig_name=ig_version if ig_version else "",
                    backend_source=backend_source if backend_source else ""
                )
            
            # Store search results and parameters in session state
            st.session_state['step1_search_level'] = search_level
            st.session_state['step1_found_files'] = found_files
            st.session_state['step1_search_params'] = {
                'resource_name': resource_name,
                'ig_version': ig_version,
                'backend_source': backend_source
            }
            
            if found_files:
                st.success(f"✅ Found {len(found_files)} mapping table(s) at level: **{search_level}**")
            else:
                st.warning("⚠️ No existing mapping tables found. Please create one in Step 0 first.")
    
    # Display search results if available
    if 'step1_found_files' in st.session_state and st.session_state['step1_found_files']:
        st.markdown("---")
        st.subheader("📚 Found Mapping Tables")
        st.caption(f"Search Level: {st.session_state['step1_search_level']}")
        
        found_files = st.session_state['step1_found_files']
        
        # Multi-select for choosing mapping tables
        st.markdown("**Select mapping tables to use for liquid generation:**")
        selected_files = []
        
        for file_path, file_name in found_files:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            is_selected = st.checkbox(
                f"📄 {file_name}",
                key=f"step1_select_{file_name}",
                value=False
            )
            
            if is_selected:
                selected_files.append((file_path, file_name, content))
                with st.expander(f"👁️ Preview: {file_name}"):
                    st.markdown(content[:500] + "..." if len(content) > 500 else content)
        
        st.session_state['step1_selected_files'] = selected_files
        
        if selected_files:
            st.info(f"✅ {len(selected_files)} mapping table(s) selected for liquid generation")
    
    # Generation section
    st.markdown("---")
    st.subheader("🚀 Generate Liquid Template")
    
    with st.form("step1_generate_form"):
        # Use search params if available
        if 'step1_search_params' in st.session_state:
            params = st.session_state['step1_search_params']
            final_resource_name = params['resource_name']
            st.info(f"**Resource:** {final_resource_name}")
        else:
            final_resource_name = st.text_input("Resource Name *", key="step1_final_resource")
        
        col_ig, col_backend = st.columns(2)
        with col_ig:
            if 'step1_search_params' in st.session_state and st.session_state['step1_search_params']['ig_version']:
                final_ig_version = st.text_input(
                    "Final IG with Version *",
                    value=st.session_state['step1_search_params']['ig_version'],
                    key="step1_final_ig"
                )
            else:
                final_ig_version = st.text_input(
                    "IG with Version *",
                    placeholder="e.g., USCore_6.1.0",
                    key="step1_final_ig"
                )
        
        with col_backend:
            if 'step1_search_params' in st.session_state and st.session_state['step1_search_params']['backend_source']:
                final_backend_source = st.text_input(
                    "Final Backend Source *",
                    value=st.session_state['step1_search_params']['backend_source'],
                    key="step1_final_backend"
                )
            else:
                final_backend_source = st.text_input(
                    "Backend Source System *",
                    placeholder="e.g., eCW, Unity",
                    key="step1_final_backend"
                )
        
        additional_info = st.text_area(
            "Additional Information (Optional)",
            height=100,
            placeholder="Provide any additional context, business rules, or special requirements for this liquid template...",
            help="Optional: Any extra context that should be considered when generating the liquid template",
            key="step1_additional_info"
        )
        
        input_json = st.text_area(
            "Input JSON (Backend Source Data) *",
            height=200,
            placeholder='{"diagnosis_code": "E11.9", "diagnosis_date": "2024-01-15"}',
            help="Paste the backend source data structure",
            key="step1_input_json"
        )
        
        with st.expander("⚙️ Advanced Options"):
            col_temp, col_tokens = st.columns(2)
            with col_temp:
                temperature = st.slider(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.1,
                    step=0.1,
                    help="Controls randomness",
                    key="step1_temperature"
                )
            with col_tokens:
                max_tokens = st.number_input(
                    "Max Tokens",
                    min_value=1000,
                    max_value=32000,
                    value=16000,
                    step=1000,
                    help="Maximum output length",
                    key="step1_max_tokens"
                )
        
        generate_liquid_button = st.form_submit_button(
            "⚡ Generate Liquid Template",
            use_container_width=True,
            type="primary"
        )
        
        if generate_liquid_button:
            # Validation
            if not final_resource_name:
                st.error("❌ Please provide Resource Name")
                st.stop()
            
            if not final_ig_version:
                st.error("❌ Please provide IG with Version")
                st.stop()
            
            if not final_backend_source:
                st.error("❌ Please provide Backend Source")
                st.stop()
            
            if not input_json:
                st.error("❌ Please enter Input JSON")
                st.stop()
            
            is_valid, error_msg = validate_json(input_json)
            if not is_valid:
                st.error(f"❌ Invalid JSON: {error_msg}")
                st.stop()
            
            # Check if mapping tables are selected
            if 'step1_selected_files' not in st.session_state or not st.session_state['step1_selected_files']:
                st.error("❌ Please search and select at least one mapping table")
                st.stop()
            
            try:
                # Get prompt builder from services
                import sys
                sys.path.insert(0, str(Path(__file__).parent))
                from services.prompt_builder_service import PromptBuilderService
                prompt_builder = PromptBuilderService()
                
                # Prepare mapping table docs from selected files
                mapping_table_docs = [content for _, _, content in st.session_state['step1_selected_files']]
                
                # Build prompt using liquid_mapping_generation_prompt.md
                with st.spinner("📝 Building Liquid generation prompt..."):
                    prompt = prompt_builder.build_liquid_mapping_generation_prompt(
                        resource_name=final_resource_name,
                        ig_name=final_ig_version.split('_')[0] if '_' in final_ig_version else final_ig_version,
                        ig_version=final_ig_version,
                        backend_source=final_backend_source,
                        input_json=input_json,
                        mapping_table_docs=mapping_table_docs,
                        additional_info=additional_info if additional_info and additional_info.strip() else None
                    )
                
                with st.expander("🔍 View Generated Prompt (for debugging)"):
                    st.text(prompt)
                
                # Generate
                with st.spinner("🤖 Generating Liquid template..."):
                    generated_liquid = asyncio.run(
                        generate_content(
                            prompt=prompt,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                    )
                
                st.success("✅ Liquid template generated successfully!")
                
                # Store in session state for save/download buttons
                st.session_state['step1_generated_liquid'] = generated_liquid
                st.session_state['step1_liquid_resource_name'] = final_resource_name
                st.session_state['step1_liquid_ig_version'] = final_ig_version
                st.session_state['step1_liquid_backend_source'] = final_backend_source
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                with st.expander("🐛 View Error Details"):
                    st.exception(e)
    
    # Display and save/download section for liquid template
    if 'step1_generated_liquid' in st.session_state and st.session_state['step1_generated_liquid']:
        st.markdown("---")
        with st.expander("⚡ View Generated Liquid Template", expanded=True):
            st.code(st.session_state['step1_generated_liquid'], language="liquid")
        
        # Save options for liquid template
        st.markdown("---")
        st.subheader("💾 Liquid Template - Save Options")
        
        col_save_liquid, col_download_liquid = st.columns(2)
        
        with col_save_liquid:
            if st.button("✅ Save Liquid Template to Dataset", use_container_width=True, type="primary", key="step1_save_liquid"):
                try:
                    # Retrieve from session state
                    liquid_content = st.session_state.get('step1_generated_liquid')
                    res_name = st.session_state.get('step1_liquid_resource_name')
                    ig_ver = st.session_state.get('step1_liquid_ig_version')
                    backend = st.session_state.get('step1_liquid_backend_source')
                    
                    if not liquid_content:
                        st.error("❌ No content to save. Please generate liquid template first.")
                    else:
                        with st.spinner("💾 Saving liquid template..."):
                            saved_path = file_storage_service.save_liquid_template(
                                content=liquid_content,
                                resource_name=res_name.capitalize(),
                                ig_version=ig_ver,
                                backend_source=backend
                            )
                        st.success(f"✅ Saved to: `{saved_path}`")
                except Exception as e:
                    st.error(f"❌ Error saving file: {str(e)}")
                    with st.expander("🐛 View Error Details"):
                        st.exception(e)
        
        with col_download_liquid:
            # Use session state for download
            liquid_to_download = st.session_state.get('step1_generated_liquid')
            res_name = st.session_state.get('step1_liquid_resource_name')
            ig_ver = st.session_state.get('step1_liquid_ig_version')
            backend = st.session_state.get('step1_liquid_backend_source')
            
            filename = f"{res_name.capitalize()}.{ig_ver}.{backend}.liquid"
            st.download_button(
                label="⬇️ Download Liquid Template",
                data=liquid_to_download,
                file_name=filename,
                mime="text/plain",
                use_container_width=True,
                key="step1_download_liquid"
            )


def main():
    """Main Streamlit application"""
    logger.info("=" * 80)
    logger.info("Liquid Mapper Application Started")
    logger.info("=" * 80)
    
    st.title("💧 Liquid Mapper - FHIR Mapping Tool")
    st.markdown("Generate mapping tables and liquid templates for FHIR resources.")
    
    # Sidebar navigation
    with st.sidebar:
        st.header("Navigation")
        st.markdown("---")
        
        step = st.radio(
            "Select Step:",
            [
                "Step 0: Generate Mapping Table",
                "Step 1: Generate Liquid Template"
            ],
            index=0
        )
        
        st.markdown("---")
        if step == "Step 0: Generate Mapping Table":
            st.info("💡 **Step 0** generates mapping table documentation from input JSON with optional Liquid template and reference mappings.")
        elif step == "Step 1: Generate Liquid Template":
            st.info("💡 **Step 1** generates Liquid templates from existing mapping table documentation.")
        
        st.markdown("---")
        st.markdown("### About")
        st.markdown("""
        This tool helps you:
        - Generate mapping table documentation
        - Create Liquid templates
        - Manage FHIR resource mappings
        """)
    
    # Display selected step
    logger.info(f"User selected step: {step}")
    if step == "Step 0: Generate Mapping Table":
        step_0_generate_mapping_table()
    elif step == "Step 1: Generate Liquid Template":
        step_1_generate_liquid_template()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        st.error(f"An unexpected error occurred: {str(e)}")
