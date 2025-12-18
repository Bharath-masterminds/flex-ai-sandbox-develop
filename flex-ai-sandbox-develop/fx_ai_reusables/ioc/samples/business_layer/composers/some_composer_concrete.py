import logging
from typing import Optional

from fx_ai_reusables.ioc.samples.business_layer.composers.interfaces.some_composer_interface import ISomeComposer
from fx_ai_reusables.ioc.samples.business_layer.managers.interfaces.animal_interface import IAnimalManager

# "Composer" is just a way to have an example class, that needs (one of) the IAnimalManagers in a constructor.
class SomeComposerConcrete(ISomeComposer):
    def __init__(self, animal_manager: IAnimalManager, logger: Optional[logging.Logger] = None):
        self._animal_manager = animal_manager
        self._logger = logger or logging.getLogger(__name__)

    def do_something_with_injected_manager(self) -> None:
        # Method no longer returns anything
        self._logger.info("Calling animal manager speak method")
        result: str = self._animal_manager.speak()
        self._logger.info(f"Animal says: {result}")
