# LangChain components
from typing import Any

from langchain_core.messages import BaseMessage


class LlmReporter:
    """display pieces of information for BaseMessage(s)."""

    @staticmethod
    async def show_type(resp: BaseMessage):

        # Resp is an instance of AIMessage(langchain)
        print(type(resp))

    @staticmethod
    async def show_keys(resp: BaseMessage):

        # available keys in the response message
        print(resp.__dict__.keys())

    @staticmethod
    async def show_content(resp: BaseMessage):

        # available keys in the response message
        print(resp.content)

    @staticmethod
    async def show_usage_costs(resp: BaseMessage):
        print("input_tokens", resp.usage_metadata.get("input_tokens"))
        print("output_tokens", resp.usage_metadata.get("output_tokens"))
        print("total_tokens", resp.usage_metadata.get("total_tokens"))

    @staticmethod
    async def show_keys_for_many(responses: list[BaseMessage]):
        for response in responses:
            await LlmReporter.show_keys(response)

    @staticmethod
    async def show_type_for_many(responses: list[BaseMessage]):
        for response in responses:
            await LlmReporter.show_type(response)

    @staticmethod
    async def show_content_for_many(responses: list[BaseMessage]):
        for response in responses:
            await LlmReporter.show_content(response)

    @staticmethod
    async def show_usage_costs_for_many(responses: list[BaseMessage]):
        for response in responses:
            await LlmReporter.show_usage_costs(response)

    @staticmethod
    async def show_content_for_dictionary_many(response_dict: dict[str, Any]):
        for key, value in response_dict.items():
            await LlmReporter.show_content_for_dictionary(key, value)

    @staticmethod
    async def show_content_for_dictionary(key:str, value:Any):
            print(f"{key}: {getattr(value, 'content', None)}")