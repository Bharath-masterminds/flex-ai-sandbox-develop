from dataclasses import dataclass

from fx_ai_reusables.configmaps.interfaces.config_map_retriever_interface import IConfigMapRetriever
from fx_ai_reusables.environment_loading.constants import (
    DEFAULT_WAIT_RANDOM_EXPONENTIAL_MIN,
    DEFAULT_WAIT_RANDOM_EXPONENTIAL_MAX,
    DEFAULT_STOP_AFTER_ATTEMPT_COUNT,
    ENV_PIECE_MEAL_WAIT_RANDOM_EXPONENTIAL_MIN,
    ENV_PIECE_MEAL_WAIT_RANDOM_EXPONENTIAL_MAX,
    ENV_PIECE_MEAL_STOP_AFTER_ATTEMPT_COUNT
)
from fx_ai_reusables.secrets.interfaces.secret_retriever_interface import ISecretRetriever

@dataclass(frozen=True)
class PieceMealVectorStoreWriterDecoratorSettings:
    wait_random_exponential_min: int
    wait_random_exponential_max: int
    stop_after_attempt_count: int

    @staticmethod
    async def hydrate(config_map_retriever: IConfigMapRetriever, secrets_retriever: ISecretRetriever) -> "PieceMealVectorStoreWriterDecoratorSettings":
        return PieceMealVectorStoreWriterDecoratorSettings(
            wait_random_exponential_min=int(
                await config_map_retriever.retrieve_optional_config_map_value(
                    ENV_PIECE_MEAL_WAIT_RANDOM_EXPONENTIAL_MIN
                ) or DEFAULT_WAIT_RANDOM_EXPONENTIAL_MIN
            ),
            wait_random_exponential_max=int(
                await config_map_retriever.retrieve_optional_config_map_value(
                    ENV_PIECE_MEAL_WAIT_RANDOM_EXPONENTIAL_MAX
                ) or DEFAULT_WAIT_RANDOM_EXPONENTIAL_MAX
            ),
            stop_after_attempt_count=int(
                await config_map_retriever.retrieve_optional_config_map_value(
                    ENV_PIECE_MEAL_STOP_AFTER_ATTEMPT_COUNT
                ) or DEFAULT_STOP_AFTER_ATTEMPT_COUNT
            )
        )

