import asyncio
import logging

from fx_ai_reusables.ioc.samples.business_layer.composers.interfaces.some_composer_interface import ISomeComposer
from fx_ai_reusables.ioc.samples.ioc.composition_root import MyCompositionRoot

# sample usage
async def main():
    logging.basicConfig(
        level=logging.INFO,  # or DEBUG
        format='%(asctime)s %(levelname)s %(message)s'
    )


    container: MyCompositionRoot = MyCompositionRoot()
    controller_instance:ISomeComposer = container.get_application_entry_class()  # First get the instance
    controller_instance.do_something_with_injected_manager()  # Then call methods on the instance


    logging.info("ioc_sample_entrypoint.py has completed.")


# Run the main function
asyncio.run(main())
