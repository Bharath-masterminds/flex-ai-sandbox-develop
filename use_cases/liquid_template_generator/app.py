import asyncio
import logging
import streamlit as st

# from fx_ai_reusables.environment_fetcher import IEnvironmentFetcher
# from fx_ai_reusables.environment_fetcher.concrete_dotenv import EnvironmentFetcher
from use_cases.liquid_template_generator.runners.interfaces.stream_lit_runner_interface import IStreamLitRunner
from use_cases.liquid_template_generator.ioc.composition_root import MyCompositionRoot

@st.cache_resource
def get_ioc_container() -> MyCompositionRoot:
    """
    Create and cache the IoC container to ensure singletons work across Streamlit reruns.
    This prevents the container from being recreated on every Streamlit interaction.
    """
    container = MyCompositionRoot()   

     # load env variables
    container.get_env_fetcher().load_environment(None, override=True, current_working_directory=True)
    
    return container
# sample usage
async def main():
    logging.basicConfig(
        level=logging.INFO,  # or DEBUG
        format='%(asctime)s %(levelname)s %(message)s'
    )

    try:
        # Get cached IoC container (created only once across all Streamlit reruns)
        container: MyCompositionRoot = get_ioc_container()

        controller_instance:IStreamLitRunner = container.get_application_entry_class()  # First get the instance    
        
        # Authentication and app logic is now handled in the controller
        controller_instance.do_something_with_injected_manager()  # Then call methods on the instance
        
    except ValueError as e:
        # Handle HashiCorp Vault configuration errors
        logging.error(f"Configuration error (likely HashiCorp Vault): {e}")
        st.error(f"Configuration Error: {e}")
        st.info("Please check your HashiCorp Vault configuration (HASHIVAULT_* environment variables)")
        return
    except Exception as e:
        # Handle other initialization errors
        logging.error(f"Application initialization error: {e}")
        st.error(f"Application Error: {e}")
        return


    logging.info("ioc_stream_lit_for_liquid_template.py has completed.")


# Run the main function
asyncio.run(main())
