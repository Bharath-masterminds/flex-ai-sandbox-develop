from dataclasses import dataclass, field

@dataclass(frozen=True)
class SecretDto:
    """Data transfer object for secrets."""
    secret_name: str
    _secret_value: str = field(repr=False)

    @property
    def secret_value(self) -> str:
        return self._secret_value

    def __str__(self) -> str:
        # Prevent secrets from appearing in logs
        return f"SecretDto(secret_name='{self.secret_name}', secret_value='***')"
