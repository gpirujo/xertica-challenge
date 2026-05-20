import json
import logging

from tools import falkordb_tools
from tools.llm_tools import get_llm

logger = logging.getLogger(__name__)

EDGE_CLASSIFICATION_CATALOGUE = """# Catálogo de Clasificación de Edges — Grafo de Normas Regulatorias

## Propósito

Este documento define los tipos de relación entre artículos/documentos regulatorios, la dirección de los edges en el grafo, y la semántica de expansión para el sistema de recuperación híbrido (GraphRAG).

**Uso previsto:** pasarle este catálogo a un LLM que analice el texto de una norma, detecte referencias a otros documentos, y devuelva una lista de edges a crear en el grafo.

---

## Modelo de datos del edge

Cada edge tiene la forma:

```
(source_doc, source_art) --[TIPO]--> (target_doc, target_art)
```

Donde `source` es el documento que **contiene la referencia** y `target` es el documento **referenciado**.

---

## Tipos de edge y semántica de expansión

### TIPO 1 — `REFERENCES`
**Semántica:** el artículo fuente remite al artículo destino para mayor detalle, definición o procedimiento. El destino sigue vigente e independiente.

**Dirección de expansión:** cuando el **source** es recuperado por el retriever → traer el **target**.

**Patrones de superficie que generan este tipo:**

| Patrón | Ejemplo del corpus |
|--------|--------------------|
| `Ver también Art. [N]` | CO/001/2021 Art.2: "Ver también Art. 8 sobre criterios de umbrales monetarios" |
| `Ver también Art. [N] de la presente circular/disposición` | MX/008/2023 Art.15: "Ver también Art. 22 para los umbrales generales" |
| `Este artículo complementa lo dispuesto en el Art. [N]` | CO/001/2021 Art.3: "Este artículo complementa lo dispuesto en el Art. 15" |
| `Esta disposición complementa el Art. [N]` | CO/001/2021 Art.15: "Esta disposición complementa el Art. 3 y el Art. 18" |
| `Este artículo referencia [Norma] Art.[N]` | MX/008/2023 Art.8: "Este artículo referencia Art. 22 para el caso de PEPs" |
| `conforme a [lo establecido en] [Norma] Art.[N]` | PE/Circ001/2020 Art.5: "conforme a la Resolución SBS N° 2660-2015 Art.12" |
| `conforme a [Norma]` (sin artículo específico) | MX/003/2020 Art.8: "conforme a la Disposición 008/2023 Art.3" |
| `de conformidad con [lo establecido en] [Norma] Art.[N]` | PE/Circ001/2020 Art.10: "de conformidad con la Resolución SBS N° 2660-2015 Art.12" |
| `establecido/s en [Norma] Art.[N]` | CO/004/2021 Art.7: "los plazos establecidos en la Circular 001/2021 Art.4" |
| `previsto/s en [Norma] Art.[N]` | MX/003/2020 Art.8: "El escalamiento previsto en la Disposición 008/2023 Art.8" |
| `dispuesto en [Norma] Art.[N]` | — |
| `hace referencia [a] [Norma] Art.[N]` | CO/003/2023 Art.4: "reportes a que hace referencia la Circular 001/2021 Art.3" |
| `se rigen por [Norma] Art.[N]` | PE/Circ002/2022 Art.1: "Las definiciones sustantivas se rigen por la Resolución SBS N° 2660-2015 Art.20" |
| `deberá interpretarse conjuntamente con [Norma]` | PE/4838/2021 Art.5: "deberá interpretarse conjuntamente con el presente artículo" |

---

### TIPO 2 — `UPDATED_BY`
**Semántica:** el artículo fuente (norma **vieja**) declara que fue actualizado, ampliado o complementado por el artículo destino (norma **nueva**). La norma nueva es la vigente o la más completa.

**Dirección de expansión:** cuando el **source** (viejo) es recuperado → traer el **target** (nuevo).

**Patrones de superficie que generan este tipo:**

| Patrón | Ejemplo del corpus |
|--------|--------------------|
| `ha sido actualizado por [Norma] Art.[N]` | CO/001/2021 Art.3: "han sido actualizados por la Circular 003/2023 Art.4" |
| `ha sido complementado por [Norma] Art.[N]` | CO/001/2021 Art.19: "ha sido complementado por la Circular 003/2023 Art.9" |
| `ha sido modificado por [Norma] Art.[N]` | — |
| `ha sido ampliado por [Norma] Art.[N]` | CO/001/2021 Art.15: "han sido ampliados por la Circular 002/2022 Art.11" |
| `fue ampliado a [...] por [Norma] Art.[N]` | CO/001/2021 Art.17: "fue ampliado a setenta y dos (72) horas por la Circular 002/2022 Art.6" |
| `han sido actualizados/complementados por [Norma] Art.[N]` | PE/2660/2015 Art.10: "han sido complementados por la Resolución SBS N° 4838-2021 Art.5" |

> **Nota de implementación:** estos patrones aparecen siempre en el documento *viejo* apuntando al *nuevo*. El edge generado es `viejo → nuevo` con tipo `UPDATED_BY`. La expansión sigue ese edge hacia adelante (target).

---

### TIPO 3 — `DEROGATED_BY`
**Semántica:** el artículo/documento fuente (norma **derogada**) es reemplazado en su totalidad o en una parte por el artículo destino (norma **derogante**). La norma derogante es la vigente.

**Dirección de expansión:** cuando el **source** (derogado) es recuperado → traer el **target** (derogante). El contenido del source ya no aplica.

**Patrones de superficie que generan este tipo:**

| Patrón | Ejemplo del corpus |
|--------|--------------------|
| `Deroga [Norma]` | CO/001/2021 Art.22: "Deroga la Circular 005/2019 en su totalidad" |
| `deroga expresamente [el mecanismo de] [Norma] Art.[N]` | CO/002/2022 Art.12: "deroga expresamente el mecanismo establecido en la Circular 001/2021 Art.18" |
| `queda sin efecto` | CO/002/2022 Art.12: "La tabla de equivalencias... queda sin efecto" |
| `reemplaza [a] [Norma]` | CO/003/2023 Art.4: "reemplaza al sistema anterior" |
| `sustituye [a] [Norma]` | — |

> **Nota de implementación:** estos patrones aparecen en el documento *nuevo* (el que deroga). El edge se construye al revés: `target (derogado) → source (derogante)` — es decir, hay que invertir la dirección al crear el edge: el derogado apunta al derogante.

---

### TIPO 4 — `MODIFIES`
**Semántica:** el artículo fuente (norma **modificante**, generalmente posterior) reemplaza el texto de un artículo específico del destino (norma **original**). El texto original ya no es el vigente para ese artículo.

**Dirección de expansión:** cuando el **target** (original) es recuperado → traer el **source** (modificante).

> Esto implica seguir el edge en sentido **inverso**: target → source.

**Patrones de superficie que generan este tipo:**

| Patrón | Ejemplo del corpus |
|--------|--------------------|
| `modifica [el mecanismo de] [Norma] Art.[N]` | CO/002/2022 Art.5: "modifica el mecanismo de cálculo establecido en la Circular 001/2021 Art.18" |
| `El artículo [N] de [Norma] queda modificado en los siguientes términos` | PE/4838/2021 Art.3: "El artículo 5 de la Resolución SBS N° 2660-2015 queda modificado" |
| `El artículo [N] de [Norma] queda complementado con` | PE/4838/2021 Art.5: "El artículo 12 de la Resolución SBS N° 2660-2015 queda complementado" |
| `Nuevo texto del Art. [N] de [Norma]` | — |
| `modificado por [Norma]` | PE/Circ002/2022 Art.7: "modificado por la Resolución SBS N° 4838-2021 Art.5" |
| `modifica los artículos [N] de [Norma]` | PE/4838/2021 Preámbulo: "modifica los artículos 5, 10, 12 y 15 de la Resolución SBS N° 2660-2015" |

> **Nota de implementación:** a diferencia de `UPDATED_BY`, estos patrones aparecen en el documento *modificante* y nombran explícitamente los artículos del documento *original* que quedan reemplazados. El edge va `modificante → original` y la expansión es inversa (cuando encontrás el original, traer el modificante).

---

### TIPO 5 — `COMPLEMENTS`
**Semántica:** ambas normas son vigentes y co-aplicables. Ninguna reemplaza ni modifica a la otra; se necesitan conjuntamente para el análisis completo. La relación es simétrica.

**Dirección de expansión:** **bidireccional** — cuando cualquiera de los dos nodos es recuperado, traer el otro.

**Patrones de superficie que generan este tipo:**

| Patrón | Ejemplo del corpus |
|--------|--------------------|
| `La presente [circular/disposición/resolución] complementa [Norma]` | CO/004/2021 Preámbulo: "complementa el régimen de la Circular 001/2021" |
| `complementaria y no deroga las obligaciones de [Norma]` | CO/003/2023 Art.11: "complementa y no deroga las disposiciones de la Circular 001/2021" |
| `en concordancia con lo dispuesto en [Norma]` | CO/003/2023 Preámbulo: "en concordancia con lo dispuesto en la Circular 001/2021 y 002/2022" |
| `Las disposiciones de [Norma] que no sean expresamente modificadas continúan vigentes` | CO/003/2023 Art.1, CO/005/2022 Art.1 |
| `[Norma] continúa/n vigente/s en su integridad` | PE/4838/2021 Art.2: "la Circular SBS N° 001-2020 continúa vigente en su integridad" |
| `Su aplicación es complementaria y no sustituye [Norma]` | MX/009/2021 Art.2: "complementaria y no sustituye las obligaciones establecidas en la Disposición 003/2020" |
| `La aplicación de estas disposiciones es complementaria a [Norma]` | MX/008/2023 Art.2, MX/015/2024 Arts.1 y 12 |
| `sin perjuicio de [Norma]` | — |
| `complementa en sus aspectos procedimentales [Norma]` | PE/Circ001/2020 Art.13: "complementa en sus aspectos procedimentales la Resolución SBS N° 2660-2015" |
| `en el marco de las obligaciones de [Norma]` | PE/Circ002/2022 Preámbulo |
| `norma de jerarquía` — "En caso de conflicto, prevalecerá [Norma]" | PE/Circ001/2020 Art.1: "En caso de conflicto... prevalecerán estas últimas" |
| `Este artículo complementa y refuerza [Norma] Art.[N]` | CO/002/2022 Art.8: "Este artículo complementa y refuerza la Circular 001/2021 Art.8" |

---

## Tabla resumen para el LLM extractor

```
TIPO          DIRECCIÓN DEL EDGE    EXPANSIÓN              PREGUNTA CLAVE
──────────────────────────────────────────────────────────────────────────────
REFERENCES    source → target       encontré source         ¿El texto dice "ver",
                                    → traer target          "conforme a", "establecido
                                                            en", "previsto en"?

UPDATED_BY    source → target       encontré source         ¿El texto dice "ha sido
              (source = viejo,      (viejo) → traer         actualizado/ampliado/
              target = nuevo)       target (nuevo)          complementado por"?

DEROGATED_BY  target → source       encontré target         ¿El texto dice "Deroga",
              (target = derogado,   (derogado) → traer      "queda sin efecto",
              source = derogante)   source (derogante)      "reemplaza"?
              ⚠️ edge invertido

MODIFIES      source → target       encontré target         ¿El texto dice "queda
              (source = modif.,     (original) → traer      modificado", "nuevo texto
              target = original)    source (modif.)         del Art.", "modifica el
              expansión inversa                             Art. X de [Norma]"?

COMPLEMENTS   source ↔ target       cualquiera encontrado   ¿El texto dice "complementa
              (bidireccional)       → traer el otro         [Norma]", "en concordancia",
                                                            "continúa vigente", "no
                                                            sustituye"?
```

---

## Formato de salida esperado del LLM extractor

El LLM que analice un documento debe devolver una lista de edges en este formato JSON:

```json
[
  {
    "source_doc": "CO/002/2022",
    "source_art": "Art.12",
    "edge_type": "DEROGATED_BY",
    "target_doc": "CO/001/2021",
    "target_art": "Art.18",
    "fragment": "deroga expresamente el mecanismo de cálculo establecido en la Circular 001/2021 Art.18",
    "expansion": "inverse"
  },
  {
    "source_doc": "CO/001/2021",
    "source_art": "Art.3",
    "edge_type": "UPDATED_BY",
    "target_doc": "CO/003/2023",
    "target_art": "Art.4",
    "fragment": "han sido actualizados por la Circular 003/2023 Art.4",
    "expansion": "forward"
  }
]
```

**Campos:**
- `source_doc` / `source_art`: documento y artículo donde aparece la referencia en el texto
- `edge_type`: uno de `REFERENCES`, `UPDATED_BY`, `DEROGATED_BY`, `MODIFIES`, `COMPLEMENTS`
- `target_doc` / `target_art`: documento y artículo referenciado (puede ser `null` si no se especifica artículo)
- `fragment`: la frase exacta del texto que motivó el edge (para auditoría)
- `expansion`: `forward` (traer target cuando se encuentra source), `inverse` (traer source cuando se encuentra target), `bidirectional`

---

## Notas de implementación

**Evitar edges duplicados:** los patrones `UPDATED_BY` y `MODIFIES` pueden generar el mismo edge visto desde documentos distintos. Antes de insertar, verificar si ya existe `(source, target, type)` en el grafo.

**Referencias intra-documento:** "Ver también Art. X de la **presente** circular" apunta a un artículo del mismo documento. Crear el edge igual con `source_doc == target_doc`; son útiles para la expansión dentro del mismo instrumento normativo.

**Artículo no especificado:** cuando la referencia apunta al documento completo sin artículo (ej: "conforme a la Disposición 012/2022"), usar `target_art: null` y en la expansión traer todos los chunks del documento target rankeados por relevancia semántica con el query original.
"""


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

        prompt = (
            f"Analizá el siguiente documento normativo e identificá todas las referencias a otros documentos.\n\n"
            f"DOCUMENTO EN ANÁLISIS: {document_id}\n\n"
            f"TEXTO DEL DOCUMENTO:\n{document_content}\n\n"
            f"DOCUMENTOS CONOCIDOS DEL MISMO PAÍS (país: {country_code}):\n"
            f"{json.dumps(country_docs, ensure_ascii=False, indent=2)}\n\n"
            f"CATÁLOGO DE TIPOS DE EDGE Y PATRONES DE REFERENCIA:\n{EDGE_CLASSIFICATION_CATALOGUE}\n\n"
            "INSTRUCCIONES:\n"
            "- Identificá todas las referencias a otros documentos que aparezcan en el texto.\n"
            "- Los patrones del catálogo NO son exhaustivos: detectá referencias aunque no coincidan exactamente con los ejemplos.\n"
            "- Para cada referencia, determiná el document_id del documento referenciado usando la lista de documentos conocidos.\n"
            "- Si la referencia no coincide con ningún documento conocido, omitila.\n"
            "- El campo \"expansion\" debe ser \"forward\", \"inverse\" o \"bidirectional\" según la semántica del catálogo.\n"
            "- El campo \"fragment\" debe ser la frase exacta del texto que motivó el edge.\n"
            "- Si no encontrás ninguna referencia, devolvé una lista vacía [].\n\n"
            "Devolvé ÚNICAMENTE un JSON válido con este formato (sin texto adicional, sin markdown):\n"
            "[\n"
            "  {\n"
            "    \"target_document_id\": \"...\",\n"
            "    \"expansion\": \"forward\" | \"inverse\" | \"bidirectional\",\n"
            "    \"fragment\": \"...\"\n"
            "  }\n"
            "]"
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
        for edge in edges:
            target = edge.get("target_doc")
            if target == document_id:
                continue
            expansion = edge.get("expansion")
            if not target or expansion not in ("forward", "inverse", "bidirectional"):
                continue
            falkordb_tools.create_edge(document_id, target, expansion)
            created += 1

        logger.info("GraphLayer.index: %s — %d edges created", document_id, created)

    def expand(self, document_id: str) -> list[str]:
        return falkordb_tools.get_related_documents(document_id)
