import os

from dotenv import load_dotenv

load_dotenv()

_GRAPH_NAME = "compliance"


def _get_graph():
    from falkordb import FalkorDB

    host = os.environ.get("FALKORDB_HOST", "localhost")
    port = int(os.environ.get("FALKORDB_PORT", 6379))
    db = FalkorDB(host=host, port=port)
    return db.select_graph(_GRAPH_NAME)


def ensure_graph() -> None:
    _get_graph()


def create_document_nodes(docs: list[dict]) -> None:
    params = [
        {"document_id": d["document_id"], "country_code": d["country_code"]}
        for d in docs
    ]
    _get_graph().query(
        "UNWIND $docs AS doc "
        "MERGE (n:Document {document_id: doc.document_id}) "
        "SET n.country_code = doc.country_code",
        {"docs": params},
    )


def create_edge(source_id: str, target_id: str, expansion: str) -> None:
    _get_graph().query(
        "MERGE (a:Document {document_id: $source}) "
        "MERGE (b:Document {document_id: $target}) "
        "MERGE (a)-[:RELATED {expansion: $expansion}]->(b)",
        {"source": source_id, "target": target_id, "expansion": expansion},
    )


def get_related_documents(document_id: str) -> list[str]:
    result = _get_graph().query(
        "MATCH (a:Document {document_id: $doc_id})-[r:RELATED {expansion: 'forward'}]->(b:Document) "
        "RETURN b.document_id AS related_id "
        "UNION "
        "MATCH (a:Document)-[r:RELATED {expansion: 'inverse'}]->(b:Document {document_id: $doc_id}) "
        "RETURN a.document_id AS related_id "
        "UNION "
        "MATCH (a:Document {document_id: $doc_id})-[r:RELATED {expansion: 'bidirectional'}]->(b:Document) "
        "RETURN b.document_id AS related_id "
        "UNION "
        "MATCH (a:Document)-[r:RELATED {expansion: 'bidirectional'}]->(b:Document {document_id: $doc_id}) "
        "RETURN a.document_id AS related_id",
        {"doc_id": document_id},
    )
    return [row[0] for row in result.result_set if row[0]]


def clear_graph() -> None:
    """Delete all nodes and edges from the compliance graph."""
    _get_graph().query("MATCH (n) DETACH DELETE n")
