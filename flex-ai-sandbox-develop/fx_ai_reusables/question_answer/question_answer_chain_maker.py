from langchain.chains.base import Chain
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore

from fx_ai_reusables.llm.creators.interfaces.llm_creator_interface import ILlmCreator
from fx_ai_reusables.question_answer.interfaces.question_answer_chain_maker_interface import IQuestionAnswerChainMaker

class QuestionAnswerChainMaker(IQuestionAnswerChainMaker):


    def __init__(self, llm_creator: ILlmCreator):
        self.llm_creator: ILlmCreator = llm_creator


    async def make_chain(self, vector_store: VectorStore, return_source_documents: bool) -> Chain:

        llm: BaseChatModel = await self.llm_creator.create_llm()

        # call helper method on vector-store to access a retriever
        retriever = vector_store.as_retriever()

        # Step 5: Create a RetrievalQA chain (QA = "Question Answer")
        qa_chain: Chain = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=retriever,
            return_source_documents=return_source_documents
        )

        return qa_chain
