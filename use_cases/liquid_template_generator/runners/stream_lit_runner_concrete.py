import json
import logging
import os
from typing import Optional

import streamlit as st

from fx_ai_reusables.environment_fetcher import IEnvironmentFetcher
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever
from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.streamlit.authenticators import StreamlitAzureAuth
from use_cases.liquid_template_generator.runners.interfaces.stream_lit_runner_interface import IStreamLitRunner
from use_cases.liquid_template_generator.utils.file_handler import FileHandler
from use_cases.liquid_template_generator.utils.template_generator import TemplateGenerator
from use_cases.liquid_template_generator.utils.template_renderer import TemplateRenderer


class StreamLitRunnerConcrete(IStreamLitRunner):
    def __init__(self,
                 template_rend: TemplateRenderer,
                 template_gen: TemplateGenerator,
                 file_hand: FileHandler,
                 secret_retriever: ISecretRetriever,
                 config_map_retriever: IConfigMapRetriever,
                 azure_auth: StreamlitAzureAuth,
                 logger: Optional[logging.Logger] = None
                 ):

        self.template_rend = template_rend
        self.template_gen = template_gen
        self.file_hand = file_hand
        self.secret_retriever = secret_retriever
        self.config_map_retriever = config_map_retriever
        self.azure_auth = azure_auth
        self._logger = logger or logging.getLogger(__name__)

    def do_something_with_injected_manager(self) -> None:
        # Method no longer returns anything
        self._logger.info("stream lit super functionality")

        # Configure page settings first (before authentication check)
        st.set_page_config(
            page_title="Liquid Template Generator",
            page_icon="🧪 ",
            layout="wide",
            menu_items={
                'Get Help': None,
                'Report a bug': None,
                'About': None
            }
        )

        # Hide Streamlit deploy button and menu items (apply immediately)
        st.markdown("""
            <style>
                .reportview-container .main .block-container{{
                    padding-top: 1rem;
                }}
                #MainMenu {visibility: hidden !important;}
                .stDeployButton {display: none !important;}
                .stActionButton {display: none !important;}
                footer {visibility: hidden !important;}
                header[data-testid="stHeader"] {display: none !important;}
                .stToolbar {display: none !important;}
                div[data-testid="stToolbar"] {display: none !important;}
                .css-14xtw13.e8zbici0 {display: none !important;}
                .css-r421ms.e10yg2by1 {display: none !important;}
            </style>
            """, unsafe_allow_html=True)

        # Check authentication - will stop execution if not authenticated
        if not self.azure_auth.check_authentication():
            return

        st.title("🧪 Liquid Template Generator")
        st.markdown("Generate Liquid templates from your data using AI")

        # Initialize session state
        if 'generated_template' not in st.session_state:
            st.session_state.generated_template = ""
        if 'rendered_output' not in st.session_state:
            st.session_state.rendered_output = ""
        if 'edited_template' not in st.session_state:
            st.session_state.edited_template = ""
        if 'actual_iterations_used' not in st.session_state:
            st.session_state.actual_iterations_used = 0

        # Sidebar for configuration options
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # User info and logout
            self.azure_auth.show_user_info_sidebar()

            # Iteration settings
            st.subheader("🔄 Iteration Settings")
            max_iterations = st.slider(
                "Maximum AI iterations for template refinement:",
                min_value=1,
                max_value=10,
                value=5,
                help="Number of times the AI will attempt to fix template errors before giving up"
            )

            st.info(f"The AI will try up to **{max_iterations}** times to generate a working template.")

            # Advanced settings
            st.subheader("🔧 Advanced Settings")

            show_debug = st.checkbox(
                "Show debug information",
                value=False,
                help="Display detailed debug information in the app"
            )

            show_syntax_highlight = st.checkbox(
                "Enable syntax highlighting",
                value=True,
                help="Show syntax-highlighted template display"
            )

            if show_debug:
                st.session_state.show_debug = True
            else:
                st.session_state.show_debug = False

            st.session_state.show_syntax_highlight = show_syntax_highlight

        # Create two columns for input methods
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📝 Input Data")

            # Text input for raw data
            raw_input_data = st.text_area(
                "Paste raw input data (CSV, TXT):",
                height=200,
                placeholder="Paste your CSV or text data here..."
            )

            # File upload for input data
            uploaded_input_file = st.file_uploader(
                "Or upload input data file:",
                type=['csv', 'txt'],
                key="input_file"
            )

        with col2:
            st.subheader("📋 Output Format/Schema")

            # Text input for output schema
            raw_output_schema = st.text_area(
                "Paste JSON schema or example output:",
                height=200,
                placeholder="Paste your JSON schema or example output here..."
            )

            # File upload for output schema
            uploaded_schema_file = st.file_uploader(
                "Or upload JSON schema/example file:",
                type=['json'],
                key="schema_file"
            )

        # Additional instructions
        st.subheader("💬 Additional Instructions")
        additional_instructions = st.text_area(
            "Provide any additional instructions for template generation:",
            height=100,
            placeholder="e.g., 'Convert all dates to YYYY-MM-DD format', 'Group by category', etc."
        )

        # Transformation Logic Upload
        st.subheader("🔀 Transformation Logic")
        st.markdown("Upload detailed transformation mapping and logic (optional)")

        # File upload for transformation logic
        uploaded_transformation_file = st.file_uploader(
            "Upload transformation logic file:",
            type=['csv', 'txt'],
            key="transformation_file",
            help="Upload a CSV or TXT file containing detailed transformation mapping and steps"
        )

        # Show file info if uploaded
        if uploaded_transformation_file:
            st.info(f"📄 File: {uploaded_transformation_file.name}")
            st.info(f"📊 Size: {uploaded_transformation_file.size} bytes")

        # Process transformation logic
        transformation_logic = ""
        if uploaded_transformation_file:
            try:
                # Read the uploaded file content
                if uploaded_transformation_file.type == "text/plain" or uploaded_transformation_file.name.endswith(
                        '.txt'):
                    # Read as text file
                    transformation_logic = str(uploaded_transformation_file.read(), "utf-8")
                elif uploaded_transformation_file.type == "text/csv" or uploaded_transformation_file.name.endswith(
                        '.csv'):
                    # Read CSV and convert to readable format
                    import io
                    csv_content = str(uploaded_transformation_file.read(), "utf-8")
                    transformation_logic = f"Transformation Logic from CSV file ({uploaded_transformation_file.name}):\n\n{csv_content}"

                if st.session_state.get('show_debug'):
                    st.info(
                        f"DEBUG: Using uploaded transformation file: {uploaded_transformation_file.name} (length: {len(transformation_logic)})")
                self._logger.debug(
                    f"Using uploaded transformation file: {uploaded_transformation_file.name} (length: {len(transformation_logic)})")

            except Exception as e:
                st.error(f"Error reading transformation file: {str(e)}")
                if st.session_state.get('show_debug'):
                    st.error(f"DEBUG: Error reading transformation file: {str(e)}")
                self._logger.error(f"Error reading transformation file: {str(e)}")

        # Display transformation logic preview if available
        if transformation_logic:
            with st.expander("🔍 Transformation Logic Preview"):
                st.text_area(
                    "Transformation logic to be used:",
                    value=transformation_logic[:1000] + ("..." if len(transformation_logic) > 1000 else ""),
                    height=200,
                    disabled=True
                )
                if len(transformation_logic) > 1000:
                    st.info(f"Showing first 1000 characters. Total length: {len(transformation_logic)} characters")

        # Show priority information if both additional instructions and transformation logic are provided
        if additional_instructions.strip() and transformation_logic:
            st.info(
                "ℹ️ **Priority Note:** Additional instructions will take precedence over uploaded transformation logic file when there are conflicts.")

        # Process inputs
        # no "new it up" : file_handler = FileHandler()

        # Get input data
        input_data = None
        delimiter_info = ""
        if raw_input_data.strip():
            input_data = raw_input_data
            if st.session_state.get('show_debug'):
                st.info(f"DEBUG: Using raw input data (length: {len(input_data)})")
            self._logger.debug(f"Using raw input data (length: {len(input_data)})")

            # Check if pasted data contains delimited content
            # no new it up # file_handler = FileHandler()
            if self.file_hand._might_be_delimited_data(input_data):
                # Detect delimiter for pasted data
                detected_delimiter = self.file_hand._detect_delimiter(input_data, "pasted_data")
                delimiter_names = {',': 'comma', ';': 'semicolon', '|': 'pipe', '\t': 'tab'}
                delimiter_info = f" (detected delimiter: {delimiter_names.get(detected_delimiter, 'unknown')})"

        elif uploaded_input_file:
            input_data = self.file_hand.process_input_file(uploaded_input_file)
            if st.session_state.get('show_debug'):
                st.info(f"DEBUG: Using uploaded file: {uploaded_input_file.name}")
            self._logger.debug(f"Using uploaded file: {uploaded_input_file.name}")
            delimiter_info = " (file processed with auto-detected delimiter)"

        # Get output schema
        output_schema = None
        output_format_info = None
        if raw_output_schema.strip():
            output_format_data = self.file_hand.analyze_pasted_output_format(raw_output_schema)
            output_schema = output_format_data['content']
            output_format_info = {
                'type': output_format_data['type'],
                'confidence': output_format_data['confidence'],
                'source': 'pasted'
            }
            if st.session_state.get('show_debug'):
                st.info(
                    f"DEBUG: Using raw output format ({output_format_data['type']}, confidence: {output_format_data['confidence']:.2f})")
            self._logger.debug(
                f"Using raw output format ({output_format_data['type']}, confidence: {output_format_data['confidence']:.2f})")
        elif uploaded_schema_file:
            output_format_data = self.file_hand.process_schema_file(uploaded_schema_file)
            if output_format_data:
                output_schema = output_format_data['content']
                output_format_info = {
                    'type': output_format_data['type'],
                    'confidence': output_format_data['confidence'],
                    'source': 'file',
                    'filename': uploaded_schema_file.name
                }
                if st.session_state.get('show_debug'):
                    st.info(
                        f"DEBUG: Using uploaded format file: {uploaded_schema_file.name} ({output_format_data['type']}, confidence: {output_format_data['confidence']:.2f})")
                self._logger.debug(
                    f"Using uploaded format file: {uploaded_schema_file.name} ({output_format_data['type']}, confidence: {output_format_data['confidence']:.2f})")

        # Display output format info if available
        if output_schema and output_format_info:
            format_type_emoji = "📋" if output_format_info['type'] == 'schema' else "📄"
            confidence_text = f"confidence: {output_format_info['confidence']:.0%}"
            st.info(
                f"{format_type_emoji} Output format detected as JSON {output_format_info['type']} ({confidence_text})")

        # Display input data info if available
        if input_data and delimiter_info:
            st.info(f"📊 Input data processed{delimiter_info}")

        # Generate template button
        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            generate_button = st.button("🚀 Generate Liquid Template", type="primary", use_container_width=True)
        with col_btn2:
            st.metric("Max Iterations", max_iterations)

        if generate_button:
            if input_data:
                # Create progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                iteration_info = st.empty()

                with st.spinner("Generating Liquid template..."):
                    try:
                        #template_generator = TemplateGenerator(max_iterations=max_iterations, llm=llm)

                        # Create a callback function to update progress
                        def progress_callback(iteration, total_iterations, status):
                            progress = iteration / total_iterations
                            progress_bar.progress(progress)
                            status_text.text(f"Status: {status}")
                            iteration_info.info(f"Iteration {iteration} of {total_iterations}")
                            if st.session_state.get('show_debug'):
                                st.write(f"DEBUG: {status}")

                        # Combine additional instructions with transformation logic with proper prioritization
                        combined_instructions = ""

                        # Structure the prompt to prioritize additional instructions
                        if additional_instructions.strip() and transformation_logic:
                            combined_instructions = f"""PRIORITY INSTRUCTIONS (HIGHEST PRIORITY - OVERRIDE ANY CONFLICTS):
        {additional_instructions.strip()}

        SUPPLEMENTARY TRANSFORMATION LOGIC (LOWER PRIORITY - USE ONLY WHERE NOT CONFLICTING WITH ABOVE):
        Note: If any transformation rule below conflicts with the Priority Instructions above, always follow the Priority Instructions.

        {transformation_logic}

        CONFLICT RESOLUTION RULE:
        When there are conflicting transformation rules between Priority Instructions and Supplementary Transformation Logic, ALWAYS prioritize and follow the Priority Instructions. The Supplementary Transformation Logic should only be used for transformations not covered or conflicting with the Priority Instructions."""
                        elif additional_instructions.strip():
                            combined_instructions = additional_instructions.strip()
                        elif transformation_logic:
                            combined_instructions = transformation_logic
                        else:
                            combined_instructions = ""

                        template, actual_iterations = self.template_gen.generate_template(
                            input_data=input_data,
                            output_schema=output_schema,
                            additional_instructions=combined_instructions,
                            progress_callback=progress_callback,
                            output_format_info=output_format_info
                        )

                        st.session_state.generated_template = template
                        st.session_state.edited_template = template  # Initialize edited template
                        st.session_state.actual_iterations_used = actual_iterations  # Store actual iterations used
                        progress_bar.progress(1.0)
                        status_text.text("Template generation completed!")

                        if st.session_state.get('show_debug'):
                            st.success(f"DEBUG: Generated template (length: {len(template)})")
                        self._logger.debug(f"Generated template (length: {len(template)})")

                        # Try to render the template
                        rendered_output = self.template_rend.render_template(template, input_data)
                        st.session_state.rendered_output = rendered_output

                        if st.session_state.get('show_debug'):
                            st.success("DEBUG: Rendered output successfully")
                        self._logger.debug("Rendered output successfully")

                        # Clear progress indicators
                        progress_bar.empty()
                        status_text.empty()
                        iteration_info.empty()

                    except Exception as e:
                        progress_bar.empty()
                        status_text.empty()
                        iteration_info.empty()
                        st.error(f"Error generating template: {str(e)}")
                        if st.session_state.get('show_debug'):
                            st.error(f"DEBUG: Error in template generation: {str(e)}")
                        self._logger.error(f"Error in template generation: {str(e)}")
            else:
                st.warning("Please provide input data either by pasting text or uploading a file.")

        # Display results
        if st.session_state.generated_template:
            st.subheader("✨ Generated Liquid Template")

            # Show generation statistics
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            with col_stats1:
                st.metric("Template Length", f"{len(st.session_state.generated_template)} chars")
            with col_stats2:
                st.metric("Iterations Used", st.session_state.actual_iterations_used)
            with col_stats3:
                if st.session_state.rendered_output:
                    st.metric("Output Length", f"{len(st.session_state.rendered_output)} chars")

            # Add download button for the template
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"liquid_template_{timestamp}.liquid"

            # Determine which template to download (edited if available, otherwise generated)
            template_to_download = st.session_state.get('edited_template', st.session_state.generated_template)
            if template_to_download != st.session_state.generated_template:
                download_label = "⬇️ Download Edited Template (.liquid)"
                download_help = "Download the edited Liquid template as a .liquid file"
            else:
                download_label = "⬇️ Download Template (.liquid)"
                download_help = "Download the generated Liquid template as a .liquid file"

            st.download_button(
                label=download_label,
                data=template_to_download,
                file_name=default_filename,
                mime="text/plain",
                help=download_help,
                type="primary"
            )

            # Create tabs for different views
            tab_view, tab_edit = st.tabs(["📄 View Template", "✏️ Edit Template"])

            with tab_view:
                st.markdown("**Syntax-Highlighted Template:**")
                if st.session_state.get('show_syntax_highlight', True):
                    # Display syntax-highlighted template
                    st.code(st.session_state.generated_template, language='liquid', line_numbers=True)
                else:
                    # Display plain text template
                    st.text_area(
                        "Generated template (read-only):",
                        value=st.session_state.generated_template,
                        height=300,
                        disabled=True
                    )

                # Template analysis
                template_lines = st.session_state.generated_template.split('\n')
                liquid_tags = [line.strip() for line in template_lines if '{%' in line or '{{' in line]

                if liquid_tags:
                    with st.expander("🔍 Template Analysis"):
                        st.write(f"**Total lines:** {len(template_lines)}")
                        st.write(f"**Lines with Liquid syntax:** {len(liquid_tags)}")
                        st.write("**Liquid tags found:**")
                        for i, tag in enumerate(liquid_tags[:10], 1):  # Show first 10 tags
                            st.code(tag, language='liquid')
                        if len(liquid_tags) > 10:
                            st.write(f"... and {len(liquid_tags) - 10} more tags")

            with tab_edit:
                st.markdown("**Editable Template:**")
                # Editable template
                edited_template = st.text_area(
                    "Edit the template and click 'Render Template' to see results:",
                    value=st.session_state.get('edited_template', st.session_state.generated_template),
                    height=350,
                    key="template_editor",
                    help="Modify the Liquid template syntax. Use {% %} for logic and {{ }} for variables."
                )

                # Update edited template in session state
                st.session_state.edited_template = edited_template

                # Template validation
                col_validate, col_render = st.columns([1, 1])

                with col_validate:
                    if st.button("🔍 Validate Syntax", help="Check if the template syntax is valid"):
                        is_valid, error_msg = self.template_rend.validate_template_syntax(edited_template)
                        if is_valid:
                            st.success("✅ Template syntax is valid!")
                        else:
                            st.error(f"❌ Syntax error: {error_msg}")

                with col_render:
                    # Manual render button
                    if st.button("🔄 Render Template", type="secondary",
                                 help="Render the edited template with input data"):
                        if input_data:
                            try:
                                rendered_output = self.template_rend.render_template(edited_template, input_data)
                                st.session_state.rendered_output = rendered_output
                                st.success("✅ Template rendered successfully!")
                                if st.session_state.get('show_debug'):
                                    st.success("DEBUG: Manual render successful")
                                self._logger.debug("Manual render successful")
                                # Force a rerun to update the rendered output section
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error rendering template: {str(e)}")
                                if st.session_state.get('show_debug'):
                                    st.error(f"DEBUG: Error in manual render: {str(e)}")
                                self._logger.error(f"Error in manual render: {str(e)}")
                        else:
                            st.warning("Input data is required for rendering.")

                # Show differences if template was edited
                if edited_template != st.session_state.generated_template:
                    with st.expander("📝 Changes Made"):
                        col_orig, col_edit = st.columns(2)
                        with col_orig:
                            st.markdown("**Original Template:**")
                            st.code(st.session_state.generated_template, language='liquid')
                        with col_edit:
                            st.markdown("**Edited Template:**")
                            st.code(edited_template, language='liquid')

            # Display rendered output
            if st.session_state.rendered_output:
                st.subheader("📄 Rendered Output")

                # Try to detect output type for syntax highlighting
                output_type = "text"
                try:
                    json.loads(st.session_state.rendered_output)
                    output_type = "json"
                except:
                    if st.session_state.rendered_output.strip().startsWith('<'):
                        output_type = "html"
                    elif ',' in st.session_state.rendered_output and '\n' in st.session_state.rendered_output:
                        output_type = "csv"

                # Display with appropriate syntax highlighting
                if st.session_state.get('show_syntax_highlight', True):
                    st.code(st.session_state.rendered_output, language=output_type, line_numbers=True)
                else:
                    st.text_area(
                        "Final rendered output:",
                        value=st.session_state.rendered_output,
                        height=200,
                        disabled=True
                    )

                # Output analysis
                with st.expander("📊 Output Analysis"):
                    output_lines = st.session_state.rendered_output.split('\n')
                    st.write(f"**Output type detected:** {output_type.upper()}")
                    st.write(f"**Total characters:** {len(st.session_state.rendered_output)}")
                    st.write(f"**Total lines:** {len(output_lines)}")

                    if output_type == "json":
                        try:
                            parsed_json = json.loads(st.session_state.rendered_output)
                            if isinstance(parsed_json, dict):
                                st.write(f"**JSON keys:** {list(parsed_json.keys())}")
                            elif isinstance(parsed_json, list):
                                st.write(f"**JSON array length:** {len(parsed_json)}")
                        except:
                            pass

        self._logger.info("END END END, when/if do I fire? stream lit super functionality")

