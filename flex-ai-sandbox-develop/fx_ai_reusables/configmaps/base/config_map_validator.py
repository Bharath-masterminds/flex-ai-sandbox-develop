class ConfigMapValidator:
    """
    Mirrors the Java utility: validates that the config map name and value
    are not the same (case-insensitive) when the value is non-blank.
    """
    ERROR_MSG_CONFIG_MAP_NAME_AND_VALUE_ARE_THE_SAME = (
        'The config-map-name and config-map-value are the same.  (Is this is placeholder situation?)  (ConfigMapName="{0}")'
    )

    @staticmethod
    def check_for_name_and_value_are_same(config_map_name: str, config_map_value: str) -> None:
        """
        Raises ValueError if config_map_value is non-blank and equals config_map_name (case-insensitive).
        """
        if config_map_value is not None and config_map_value.strip() and \
           config_map_name.lower() == config_map_value.lower():
            raise ValueError(
                ConfigMapValidator.ERROR_MSG_CONFIG_MAP_NAME_AND_VALUE_ARE_THE_SAME.format(config_map_name)
            )
