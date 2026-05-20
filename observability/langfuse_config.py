import os

from dotenv import load_dotenv

load_dotenv()

_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY")

if _PUBLIC_KEY:
    from langfuse import Langfuse, get_client
    from langfuse.langchain import CallbackHandler

    Langfuse(
        public_key=_PUBLIC_KEY,
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
        base_url=os.environ.get("LANGFUSE_BASE_URL",
                 os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")),
    )

    def get_langfuse_handler(trace_id: str, session_id: str) -> CallbackHandler:
        hex_trace_id = trace_id.replace("-", "")
        return CallbackHandler(trace_context={"trace_id": hex_trace_id})

    def score_trace(trace_id: str, name: str, value) -> None:
        get_client().create_score(trace_id=trace_id, name=name, value=float(value))

    def flush() -> None:
        get_client().flush()

    langfuse_client = get_client()

else:
    try:
        from langchain_core.callbacks import BaseCallbackHandler as _LangchainBase

        class _NoOpHandler(_LangchainBase):
            pass

    except ImportError:
        class _NoOpHandler:  # type: ignore[no-redef]
            pass

    def get_langfuse_handler(trace_id: str, session_id: str) -> _NoOpHandler:
        return _NoOpHandler()

    def score_trace(trace_id: str, name: str, value) -> None:
        pass

    def flush() -> None:
        pass

    langfuse_client = None
