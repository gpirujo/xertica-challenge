import json
import logging

from tools import falkordb_tools
from tools.llm_tools import get_llm

logger = logging.getLogger(__name__)

class GraphLayer:
    def __init__(self) -> None:
        self.doc_catalog: dict[str, dict[str, str]] = {}

    def initialize(self) -> None:
        falkordb_tools.ensure_graph()
        logger.info("GraphLayer.initialize: graph ready")

    def load_catalog(self, docs: list[dict]) -> None:
        self.doc_catalog = {}
        for doc in docs:
            cc = doc["country_code"]
            doc_id = doc["document_id"]
            label = f"{doc['type']} {doc['number']}/{doc['year']} {doc['issuer']}: {doc['title']}"
            self.doc_catalog.setdefault(cc, {})[doc_id] = label

        falkordb_tools.create_document_nodes(docs)
        logger.info("GraphLayer.load_catalog: %d documents loaded", len(docs))

    def index(self, document_id: str, document_content: str, country_code: str) -> None:
        country_docs = self.doc_catalog.get(country_code, {})

        reference_patterns = {   
            "FORWARD":[
                "Ver también Art. [N]",
                "Este artículo referencia [Norma] Art.[N]",
                "conforme a [lo establecido en] [Norma] Art.[N]",
                "de conformidad con [lo establecido en] [Norma] Art.[N]",
                "establecido/s en [Norma] Art.[N]",
                "previsto/s en [Norma] Art.[N]",
                "dispuesto en [Norma] Art.[N]",
                "ha sido actualizado/complementado/modificado/ampliado por [Norma] Art.[N]",
                "han sido actualizados/complementados por [Norma] Art.[N]",
                "hace referencia [a] [Norma] Art.[N]",
                "modificado por [Norma]",
                "se rigen por [Norma] Art.[N]",
                "en concordancia con lo dispuesto en [Norma]"
            ],
            "INVERSE":[
                "Este artículo complementa lo dispuesto en el Art. [N]",
                "Esta disposición complementa el Art. [N]",
                "[Norma] que continúa/n vigente/s en su integridad",
                "Deroga [Norma]",
                "queda modificado en los siguientes términos",
                "El artículo [N] de [Norma] queda modificado/complementado",
                "Nuevo texto del Art. [N] de [Norma]",
                "reemplaza [al sistema anterior / a Norma]",
                "La presente [circular/disposición/resolución] complementa [Norma]",
                "Las disposiciones de [Norma] que no sean expresamente modificadas continúan vigentes",
                "deberá interpretarse conjuntamente con [Norma]"
            ] 
        }
        
        prompt = (
            
            f"Tenemos un catálogo con los siguientes documentos:\n"
            f"'''\n{json.dumps(country_docs, ensure_ascii=False, indent=2)}\n'''\n\n"
        
            f"Este es un catálogo NO exhaustivo de ejemplos de patrones de referencias 'FORWARD' e 'INVERSE':\n"
            f"'''\n{json.dumps(reference_patterns, ensure_ascii=False, indent=2)}\n'''\n\n"
        
            f"Analizá el siguiente documento identificá todas las referencias a otros documentos:\n\n"
            f"'''\n{document_content}\n'''\n\n"

            f"Devolvé ÚNICAMENTE un JSON válido que sea un diccionario cuyas keys sean los document_ids del catálogo de documentos y cuyos valores sean la dirección ('forward' o 'inverse') de la referencia.\n"
        
        )

        raw = get_llm().invoke(prompt).content.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else parts[0]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        
        try:
            edges = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("GraphLayer.index: invalid JSON from LLM for %s: %r", document_id, raw[:200])
            return

        created = 0
        for target_document_id, expansion in edges.items():
            if not target_document_id:
                continue
            if target_document_id == document_id:
                continue
            expansion = expansion.lower()
            if expansion not in ("forward", "inverse"):
                continue
            falkordb_tools.create_edge(document_id, target_document_id, expansion)
            created += 1

        logger.info("GraphLayer.index: %s — %d edges created", document_id, created)

    def expand(self, document_id: str) -> list[str]:
        return falkordb_tools.get_related_documents(document_id)
