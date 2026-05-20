import os

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()


def get_llm(temperature: float = 0) -> BaseChatModel:
    provider = os.environ.get("LLM_PROVIDER")
    if provider == "openrouter":
        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            model=os.environ["LLM_MODEL"],
            temperature=temperature,
        )
    raise ValueError(
        f"Unknown or missing LLM_PROVIDER: {provider!r}. Expected 'openrouter'."
    )


def get_embeddings() -> Embeddings:
    provider = os.environ.get("EMBEDDING_PROVIDER")
    if provider == "openrouter":
        return OpenAIEmbeddings(
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=os.environ["OPENROUTER_API_KEY"],
            model=os.environ["EMBEDDING_MODEL"],
        )
    raise ValueError(
        f"Unknown or missing EMBEDDING_PROVIDER: {provider!r}. Expected 'openrouter'."
    )
