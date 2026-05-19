import os

from dotenv import load_dotenv

load_dotenv()


def embed(texts: list[str]) -> list[list[float]]:
    provider = os.environ.get("EMBEDDING_PROVIDER")
    model = os.environ["EMBEDDING_MODEL"]

    if provider == "openrouter":
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url="https://openrouter.ai/api/v1",
        )
        response = client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in response.data]

    if provider == "vertexai":
        from google.cloud import aiplatform
        from vertexai.language_models import TextEmbeddingModel

        aiplatform.init(
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.environ["GOOGLE_CLOUD_LOCATION"],
        )
        embedding_model = TextEmbeddingModel.from_pretrained(model)
        results = embedding_model.get_embeddings(texts)
        return [r.values for r in results]

    raise ValueError(
        f"Unknown or missing EMBEDDING_PROVIDER: {provider!r}. "
        "Expected 'openrouter' or 'vertexai'."
    )
