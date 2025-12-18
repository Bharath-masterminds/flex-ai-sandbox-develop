from dependency_injector import containers, providers

from fx_ai_reusables.ioc.configuration.ioc_configuration import IocConfig
from fx_ai_reusables.ioc.samples.business_layer.composers.some_composer_concrete import SomeComposerConcrete
from fx_ai_reusables.ioc.samples.business_layer.composers.interfaces.some_composer_interface import ISomeComposer
from fx_ai_reusables.ioc.samples.business_layer.managers.bird_manager import BirdManager
from fx_ai_reusables.ioc.samples.business_layer.managers.cat_manager import CatManager
from fx_ai_reusables.ioc.samples.business_layer.managers.dog_manager import DogManager
from fx_ai_reusables.ioc.samples.business_layer.managers.interfaces.animal_interface import IAnimalManager


class MyCompositionRoot(containers.DeclarativeContainer):
    """
    MyCompositionRoot is the main IoC container for the application.
    Your app should not call it "My", "My" is used here to show it has no special naming requirement.
    """

    # Define configuration
    # note "private" _ to encapsulate in this class
    _config = providers.Configuration()

    # Set configuration values during container initialization
    _config.from_dict({
        "DeploymentFlavor": IocConfig.DeploymentFlavor
    })

    #PRIMARY "CHOICE" Functionality: Select between different implementations based on configuration
    # Define animal manager provider based on deployment flavor
    # note "private" _ to encapsulate in this class
    _animal_manager_resolved: IAnimalManager = providers.Selector(
        _config.DeploymentFlavor,
        DEVELOPMENTLOCAL=providers.Factory(DogManager),
        K8DEPLOYED=providers.Factory(CatManager),
        GITWORKFLOWDEPLOYED=providers.Factory(BirdManager),
    )

    # Define controller with animal manager injected
    # note "private" _ to encapsulate in this class
    _composer: ISomeComposer = providers.Factory(
        SomeComposerConcrete,
        animal_manager=_animal_manager_resolved
    )

    # below ("public") method could be named anything.  note special naming convention.
    # Use a provider to expose the ISomeComposer through a public interface
    get_application_entry_class: ISomeComposer = providers.Callable(
        lambda controller: controller,
        controller=_composer
    )
