from fx_ai_reusables.ioc.samples.business_layer.managers.interfaces.animal_interface import IAnimalManager


class CatManager(IAnimalManager):
    def speak(self) -> str:
        return "Meow!"
