from typing import Optional

class SecretValidator:
    ERROR_MSG_SECRET_NAME_AND_VALUE_ARE_THE_SAME: str = (
        'The secret-name and secret-value are the same.  (Is this is placeholder situation?)  (SecretName="%s")'
    )

    @staticmethod
    def check_for_name_and_value_are_same(secret_name: str, secret_value: Optional[str]) -> None:
        """
        Raises ValueError if secret_value is non-blank and equals secret_name (case-insensitive).
        Mirrors Java logic using StringUtils.isBlank and equalsIgnoreCase.
        """
        if secret_value is None:
            return
        if secret_value.strip() == "":
            return
        if secret_name.casefold() == secret_value.casefold():
            raise ValueError(SecretValidator.ERROR_MSG_SECRET_NAME_AND_VALUE_ARE_THE_SAME % secret_name)