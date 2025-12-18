# LangChain components
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage


class LlmWorker:
    @staticmethod
    async def invoke_llm(llm: BaseChatModel, prompt: str) -> BaseMessage:

        # Send a simple greeting to test the model
        # resp = llm.invoke("Hello, how are you?")
        resp = llm.invoke(prompt)

        return resp
