import os

class IocConfig:
    """
    Configuration class for Inversion of Control (IoC) container settings.

    This class defines the valid deployment environments and retrieves the
    current deployment flavor from environment variables. It validates that
    the specified deployment flavor is one of the allowed values.

    Attributes:
        VALID_FLAVORS (set): Set of valid deployment environment names.
        DeploymentFlavor (str): The current deployment environment,
                               retrieved from the DEPLOYMENT_FLAVOR environment variable.

    Raises:
        ValueError: If DeploymentFlavor is None or not in VALID_FLAVORS.
    """

    VALID_FLAVORS = {"DEVELOPMENTLOCAL", "K8DEPLOYED", "GITWORKFLOWDEPLOYED"}

    DeploymentFlavor = os.getenv("DEPLOYMENT_FLAVOR")

    if not DeploymentFlavor or DeploymentFlavor not in VALID_FLAVORS:
        raise ValueError(
            f"Invalid DEPLOYMENT_FLAVOR: '{DeploymentFlavor}'. "
            f"Must be one of {', '.join(VALID_FLAVORS)}."
        )
