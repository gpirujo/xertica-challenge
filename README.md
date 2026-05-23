# Compliance Agent — Sistema Multi-Agente AML/CFT

Sistema de análisis automatizado de alertas de cumplimiento normativo (AML/CFT) para entidades financieras. Orquesta tres agentes especializados con LangGraph para reducir el tiempo de resolución de alertas de 4.2 horas a menos de 30 minutos, con trazabilidad completa de cada decisión.

Desarrollado como parte del technical challenge de Xertica — Staff Engineer position.

---

## Índice

- [Arquitectura](#arquitectura)
- [Stack y decisiones de diseño](#stack-y-decisiones-de-diseño)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Cómo correrlo](#cómo-correrlo)
- [Challenge 01 — Agentes](#challenge-01--agentes)
- [Challenge 02 — RAG híbrido](#challenge-02--rag-híbrido)
- [Challenge 03 — CTO Brief](#challenge-03--cto-brief)
- [Challenge 04 — Infraestructura y CI/CD](#challenge-04--infraestructura-y-cicd)
- [Challenge 05 — Incidente PEP](#challenge-05--incidente-pep)
- [Supuestos](#supuestos)
- [Mi flujo con AI](#mi-flujo-con-ai)

---

## Arquitectura

```
                        POST /api/v1/alerts/{id}/analyze
                                      │
                               ┌──────▼──────┐
                               │   FastAPI   │
                               └──────┬──────┘
                                      │
                          ┌───────────▼─────────────┐
                          │    LangGraph Pipeline   │
                          │                         │
                          │  ┌──────────────────┐   │
                          │  │ Agente Investig. │   │
                          │  │  BigQuery (mock) │   │
                          │  │  GCS (mock)      │   │
                          │  └────────┬─────────┘   │
                          │           │             │
                          │  ┌────────▼─────────┐   │
                          │  │  Risk Analyzer   │   │
                          │  │  LLM + RAG híb.  │──────── score ≥ 9 → auto-escala
                          │  └────────┬─────────┘   │
                          │           │             │
                          │  ┌────────▼─────────┐   │
                          │  │ Decision Agent   │   │
                          │  │  LLM + audit     │   │
                          │  └────────┬─────────┘   │
                          └───────────┼─────────────┘
                                      │
                          ┌───────────▼─────────────┐
                          │     ComplianceState     │
                          │  decisión + confianza   │
                          │  regulaciones + razones │
                          │  trace_id (Langfuse)    │
                          └─────────────────────────┘

     RAG híbrido (usado por Risk Analyzer y Decision Agent):
     ┌──────────┐   ┌─────────────────┐   ┌──────────────┐
     │ pgvector │ + │ Elasticsearch   │   │  FalkorDB    │
     │  (dense) │   │ (sparse / BM25) │   │  (graph)     │
     └──────────┘   └─────────────────┘   └──────────────┘
          └────────RRF fusion────────┘          │
                        └──────── expansión ────┘
```

El pipeline completo corre dentro de GCP `us-central1` en producción, cumpliendo la restricción de datos personales. En desarrollo se usa OpenRouter como proveedor de LLM.

---

## Stack y decisiones de diseño

| Componente | Elección | Justificación |
|---|---|---|
| **Orquestación** | LangGraph | Google ADK requiere estar dentro de GCP para desarrollar; LangGraph corre en cualquier entorno y tiene soporte nativo para grafos con estado compartido |
| **LLM (dev)** | OpenRouter `auto` | Interfaz compatible con OpenAI SDK; cambiar de proveedor es solo 2 variables de entorno |
| **LLM (prod)** | Vertex AI (Gemini) | Cumple la restricción de datos dentro de GCP `us-central1`; no envía datos a APIs externas |
| **Vector store** | pgvector sobre PostgreSQL | PostgreSQL ya es parte del stack de la empresa; el equipo conoce el software y la operación |
| **Sparse search** | Elasticsearch | Elasticsearch ya es parte del stack de la empresa; aprovecha infraestructura y experiencia existentes. Evalué ParadeDB para usar un solo motor, pero preferí software conocido por el equipo y el costo adicional no es un problema |
| **Graph layer** | FalkorDB | Más liviano que Neo4j; corre en Docker sin licencia; API Cypher-compatible. No requiere ACID porque las escrituras ocurren solo durante la indexación offline; en producción el grafo es read-only |
| **Hybrid fusion** | RRF (Reciprocal Rank Fusion) | Combina rankings en lugar de scores absolutos — robusto cuando los canales tienen distribuciones distintas, sin necesidad de normalización ni calibración de pesos. Estándar de facto en búsqueda híbrida |
| **Observabilidad** | Langfuse Cloud (free tier) | Evita infraestructura adicional en dev; instrumentación nativa para LangGraph |
| **API** | FastAPI | Sin variación respecto al stack pedido |
| **Infra (prod)** | Terraform + GitHub Actions | Requerido por el challenge |

**Cloud SQL vs AlloyDB:** Se eligió Cloud SQL PostgreSQL 17 (~$50-150/mes) sobre AlloyDB (~3-5x más caro). La diferencia de performance no justifica el costo para este volumen, y Cloud SQL ya es conocido por el equipo de infraestructura.

**Elasticsearch vs Vertex AI Search:** Elasticsearch ya es parte del stack de la empresa — mismo razonamiento que PostgreSQL. El costo mayor de Vertex AI Search no se justifica para el volumen del problema.

**FalkorDB en GCE vs Spanner Graph:** Spanner Graph tiene un mínimo de ~$65/mes para un grafo de cientos de nodos regulatorios. FalkorDB en una `e2-medium` cuesta ~$30/mes y tiene API Cypher-compatible.

---

## Estructura del repositorio

```
compliance-agent/
├── agents/
│   ├── research.py          # Agente Investigador: BigQuery + GCS → ComplianceState
│   ├── risk_analyzer.py     # Agente de Riesgo: LLM con structured output → score 1–10
│   └── decision.py          # Agente de Decisión: LLM + RAG → escalate|dismiss
├── graph/
│   ├── pipeline.py          # LangGraph StateGraph, edge condicional (score ≥ 9)
│   └── state.py             # ComplianceState (TypedDict compartido)
├── rag/
│   ├── indexer.py           # PDF → artículos → pgvector + Elasticsearch + FalkorDB
│   ├── dense.py             # Búsqueda por similitud coseno (pgvector)
│   ├── sparse.py            # Búsqueda BM25 (Elasticsearch, analizador spanish)
│   ├── graph.py             # Expansión por relaciones entre artículos (FalkorDB)
│   └── retriever.py         # Hybrid retriever: RRF sobre dense y sparse + expansión graph
├── tools/
│   ├── bigquery_tools.py    # Mock BigQuery: lee fixtures/customers/*.json
│   ├── gcs_tools.py         # Mock GCS: lee fixtures/regulatory_docs/
│   ├── llm_tools.py         # Cliente LLM intercambiable (OpenRouter / Vertex AI)
│   ├── postgresql_tools.py  # Conexión pgvector
│   ├── elasticsearch_tools.py # Conexión ElasticSearch
│   └── falkordb_tools.py    # Conexión FalkorDB
├── api/
│   └── main.py              # FastAPI: POST /analyze, GET /status, GET /health
├── observability/
│   └── langfuse_config.py   # Setup Langfuse, trace_id generado antes del invoke
├── fixtures/
│   ├── alerts.json          # Alertas sintéticas de prueba
│   ├── customers/           # CUST-001..005: perfil + historial de transacciones
│   └── regulatory_docs/     # 16 documentos regulatorios sintéticos
│       ├── CO/UIAF/         # 5 circulares Colombia
│       ├── MX/CNBV/         # 5 disposiciones México
│       └── PE/SBS/          # 6 resoluciones/circulares Perú
├── infra/
│   ├── main.tf              # Cloud Run, GCS, Cloud SQL, GCE (ES + FalkorDB), IAM
│   ├── variables.tf         # Variables comentadas
│   └── outputs.tf
├── notebooks/
│   ├── chunk_size_analysis.ipynb        # Análisis del corpus para definir chunk size
│   ├── langfuse_metrics_dashboard.ipynb # Visualización de métricas de LangFuse
│   ├── smoke_test/                      # Notebooks de validación por capa
│   └── rag_evaluation/
│       ├── 01_generate_dataset.ipynb    # Genera dataset con RAGAS TestsetGenerator
│       └── 02_evaluate_rag.ipynb        # Evaluación context precision + recall
├── tests/
│   ├── test_agents.py       # Tests unitarios con LLM mockeado
│   ├── test_rag.py          # Tests de indexación y retrieval
│   ├── test_api.py          # Tests de endpoints con httpx
│   ├── test_pipeline.py     # Tests end-to-end del pipeline
│   └── test_tools.py        # Tests de acceso a los datos
├── scripts/
│   ├── metrics_report.py    # Reporte de métricas desde Langfuse
│   └── metrics_lib.py       # Recuperación de métricas de LangFuse
├── eval/
│   └── dataset.json         # Dataset de evaluación RAG
├── cto_brief.pdf            # Documento para el board (Challenge 03)
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

---

## Cómo correrlo

### Prerequisitos

- Docker y Docker Compose
- Una API key de [OpenRouter](https://openrouter.ai) (gratuita) o Vertex AI
- Una cuenta en [Langfuse Cloud](https://cloud.langfuse.com) (free tier)

### 1. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con los valores reales. Variables mínimas para correr:

```env
# LLM
OPENROUTER_API_KEY=sk-or-...
LLM_PROVIDER=openrouter
LLM_MODEL=openrouter/auto

# Langfuse (crear proyecto en cloud.langfuse.com)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Embeddings
EMBEDDING_PROVIDER=openrouter
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

Las variables de Postgres, Elasticsearch y FalkorDB tienen defaults que funcionan con `docker compose up`.

### 2. Levantar servicios

```bash
docker compose up --build
```

Levanta Postgres (pgvector), Elasticsearch, FalkorDB y la API en `localhost:8000`.

### 3. Indexar documentos regulatorios

Una sola vez al inicio (o cuando cambie el corpus):

```bash
docker compose exec api python -c "
from rag.indexer import index_documents
index_documents(before=lambda doc: print('Indexando:', doc['document_id']))
print('Indexación completa')
"
```

Indexa los 16 documentos de `fixtures/regulatory_docs/` en pgvector, Elasticsearch y FalkorDB.

### 4. Analizar una alerta

```bash
curl -X POST http://localhost:8000/api/v1/alerts/ALERT-001/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-004",
    "alert_type": "transferencia_internacional",
    "description": "Transferencia de $45,000 USD a cuenta en jurisdicción de alto riesgo",
    "severity": "medium",
    "created_at": "2024-12-10"
  }' | python3 -m json.tool
```

La respuesta incluye: score de riesgo (1–10), nivel (critical/high/medium/low), anomalías detectadas, decisión (escalate/dismiss), confianza, regulaciones aplicables, razonamiento paso a paso, y `trace_id` para consultar en Langfuse.

### 5. Ver trazas en Langfuse

Con el `trace_id` de la respuesta anterior:

```
https://cloud.langfuse.com/project/{project_id}/traces/{trace_id}
```

Muestra los tres nodos del pipeline, latencia por nodo, tokens y costo estimado por alerta.

### 6. Correr tests

```bash
docker compose exec api pytest tests/ -v --cov=. --cov-report=term-missing
```

La cobertura mínima requerida por el CI/CD es 60%.

### 7. Levantar JupyterLab (opcional)

```bash
docker compose --profile jupyter up
```

Levanta un contenedor con JupyterLab dentro del mismo entorno Docker, con acceso a los mismos servicios que usa la API (Postgres, Elasticsearch, FalkorDB). Es útil para exploración interactiva, smoke tests y el notebook de evaluación RAG.

Al iniciar, las últimas líneas del output del contenedor muestran la URL de acceso:

```
http://127.0.0.1:8888/lab?token={token}
```

Antes de ejecutar cualquier notebook, instalar los requirements dentro del contenedor:

```bash
docker exec -it repo-jupyter-1 /opt/conda/bin/pip install --no-cache-dir -r ../requirements.txt
```

---

## Challenge 01 — Agentes

### Estado compartido: `ComplianceState`

Todos los agentes comparten un `TypedDict` que fluye por el pipeline:

| Grupo | Campos |
|---|---|
| Input | `alert`, `trace_id` |
| Research | `customer`, `transaction_history`, `transaction_summary`, `documents`, `investigador_status` |
| Risk | `risk_score` (1–10), `risk_justification`, `anomalies`, `risk_summary`, `risk_analyzer_status` |
| Decision | `decision` (escalate\|dismiss), `confidence`, `applicable_regulations`, `reasoning_steps`, `final_report`, `decision_status` |

### Agente Investigador (`agents/research.py`)

**Responsabilidad:** construir el contexto completo del caso a partir del `alert_id`.

1. Obtiene el perfil del cliente desde BigQuery (`get_customer_data`)
2. Obtiene los últimos 90 días de transacciones; anota `is_international` comparando `counterparty_country` con el país de origen del cliente
3. Calcula `transaction_summary`: volumen total, promedio, máximo, conteo de transacciones internacionales, conteo de transacciones flaggeadas por XGBoost
4. Recupera documentos regulatorios mediante `hybrid_retrieve(query, country_code)` — el `country_code` filtra por jurisdicción
5. Obtiene el contenido de los documentos desde GCS

No invoca LLM. Es puro orquestación de herramientas.

### Agente de Análisis de Riesgo (`agents/risk_analyzer.py`)

**Responsabilidad:** evaluar el riesgo del caso con output estructurado.

Recibe el contexto del Agente Investigador y produce:
- Score 1–10 con justificación explícita
- Lista de anomalías detectadas comparadas contra el histórico
- Resumen en lenguaje natural para el analista humano
- IDs de regulaciones aplicables

Usa `.with_structured_output()` para forzar la estructura del output. El prompt del sistema lo posiciona como experto AML/CFT con conocimiento de UIAF (Colombia), CNBV (México) y SBS (Perú).

**Edge condicional:** si `risk_score >= 9`, el pipeline hace auto-escalación sin invocar al Agente de Decisión — el resultado del análisis es suficiente para la decisión.

### Agente de Decisión (`agents/decision.py`)

**Responsabilidad:** producir una decisión final con audit trail completo.

Recibe el análisis de riesgo y produce:
- Decisión: `escalate_human` o `dismiss`
- Nivel de confianza (0–1)
- Regulaciones aplicables con citas específicas
- Razonamiento paso a paso (mínimo 3 pasos) — este campo es el audit trail
- Reporte final para el analista humano

Diseñado como "juez conservador": el prompt del sistema le instruye a ser conservador con PEPs y a solo evaluar la evidencia ya reunida, sin inferir información adicional.

### Pipeline LangGraph (`graph/pipeline.py`)

```
research → risk_analyzer → [score < 9] → decision_agent → END
                        ↘ [score ≥ 9] → END (auto-escala)
```

Cada ejecución genera un `trace_id` UUID antes del `invoke`, que se propaga al handler de Langfuse para correlacionar la traza completa.

---

## Challenge 02 — RAG híbrido

### Corpus regulatorio

16 documentos sintéticos organizados por jurisdicción:

- **Colombia / UIAF** (5): operaciones sospechosas, umbrales de beneficiario final, sanciones financieras, transferencias electrónicas, activos virtuales
- **México / CNBV** (5): operaciones en efectivo, sanciones financieras, beneficiario final, PEPs y transferencias internacionales, instituciones de tecnología financiera
- **Perú / SBS** (6): gestión de riesgo LA/FT, operaciones sospechosas, transferencias electrónicas, régimen PEPs, beneficiario final, registros digitales

Los documentos tienen referencias cruzadas entre sí ("en concordancia con lo dispuesto en el Artículo X", "deroga la Circular N°", etc.).

### Chunking

**Tamaño elegido: artículo completo** (sin overlap).

El chunk size óptimo se derivó de un análisis del corpus real (`notebooks/chunk_size_analysis.ipynb`): el p95 de longitud de artículo es ~200 tokens. Para documentos regulatorios, el artículo es la unidad natural de significado — un inciso fuera de su artículo padre pierde contexto. Chunks más pequeños aumentan la precisión de recuperación pero rompen la coherencia semántica; chunks más grandes diluyen la señal. Dividir en artículos da lo mejor de los dos mundos para este corpus.

**Implementación:** el indexer (`rag/indexer.py`) divide cada documento con regex sobre `Artículo \d+` / `Art. \d+`. Cada artículo se indexa como una unidad en dense (pgvector) y sparse (Elasticsearch). En el grafo (FalkorDB), la unidad de indexación es el documento completo.

### Dense search (pgvector)

Embeddings de artículos almacenados en PostgreSQL con la extensión `pgvector`. Búsqueda por similitud coseno. El modelo de embeddings es configurable via `EMBEDDING_MODEL` en `.env` — debe ser el mismo en indexación y en consulta.

### Sparse search (Elasticsearch)

Indexación con el analizador `spanish`, que aplica:
- **Stemming**: "transferencias" → "transfer", "políticamente" → "politic"
- **Stopwords**: elimina "de", "la", "en", etc.
- **Normalización de tildes**: "artículo" y "articulo" son equivalentes

El texto pasa por normalización NFC en Python antes de enviarse a ES para evitar inconsistencias de encoding. Se evaluó el analizador `icu_analyzer` (mejor soporte Unicode) pero `spanish` es suficiente para este corpus y no requiere plugin adicional.

### Graph layer (FalkorDB)

Modela las relaciones entre documentos regulatorios como un grafo dirigido con edges tipados. Los tipos de relación y su dirección determinan cómo se expande el contexto:

- **Forward** (`A → B`, "véase el Artículo B"): cuando A es recuperado como relevante, se expande hacia B
- **Inverse** (`A → B`, "deroga la Circular B"): cuando B es recuperado, se expande hacia A — porque A es la norma vigente
- **Bidirectional**: expansión en ambas direcciones

El catálogo de frases que expresan cada tipo de relación fue construido manualmente sobre el corpus sintético (se tiene cobertura completa porque los documentos son conocidos). En producción con documentos reales, este catálogo debería construirse con un LLM que analice el corpus antes de indexar.

### Hybrid retrieval: RRF

Dense y sparse se combinan con **Reciprocal Rank Fusion (RRF)**:

```
score(d) = Σ 1 / (k + rank_canal(d))
```

donde `k = 60` (valor estándar) y la suma es sobre los dos canales. RRF fue elegido sobre weighted sum y cross-encoder reranking por tres razones: no requiere normalizar scores de distribuciones distintas (pgvector devuelve similitud coseno 0–1, ES devuelve BM25 sin cota superior), no requiere calibrar pesos manualmente, y es robusto cuando un canal no tiene resultados para una query.

Una vez obtenida la lista fusionada de documentos más relevantes, el canal de grafo la expande: para cada documento en el resultado, se siguen los edges de FalkorDB según su tipo y dirección, y se agregan los documentos referenciados. El resultado final incluye tanto los documentos recuperados por similitud como sus referencias regulatorias relacionadas.

### Evaluación del RAG

**Framework: RAGAS**

RAGAS fue elegido sobre DeepEval por su diseño específico para RAG y por el `TestsetGenerator`, que genera el dataset de evaluación sintético directamente desde el corpus de normativa. DeepEval es más potente para pipelines agénticos completos, pero su costo por ejecución es mayor (casi todas sus métricas requieren LLM-as-judge).

**Métricas implementadas:**

**Context Precision:** proporción de chunks recuperados que son relevantes para la pregunta. Mide si el retriever trae ruido.

```
Context Precision = |chunks relevantes recuperados| / |chunks recuperados|
```

Implementada como LLM-as-judge en RAGAS: el modelo evalúa si cada chunk recuperado aporta información necesaria para responder la pregunta.

**Context Recall:** proporción del ground truth cubierta por los chunks recuperados. Mide si el retriever trae suficiente.

```
Context Recall = |claims del ground truth soportados por contexto| / |claims totales del ground truth|
```

El modelo usado como juez es configurable independientemente del modelo de los agentes. En producción se usaría un modelo de mayor calidad; en desarrollo se usó un modelo más económico. El dataset adjunto (`eval/dataset.json`) fue generado con el modelo económico — en producción, un dataset generado con un modelo mejor produciría evaluaciones más precisas. Las corridas de evaluación completa son manuales (no parte del CI/CD).

El dataset de evaluación (`eval/dataset.json`) incluye tres tipos de preguntas:
- **Factual simple:** respuesta en un solo artículo — mide el baseline del retriever
- **Multi-documento:** requiere combinar artículos de distintas secciones — mide el graph layer
- **Razonamiento regulatorio:** interpreta una norma, no la extrae literalmente — mide el LLM

Ver `notebooks/rag_evaluation/` para la generación del dataset y la evaluación completa.

---

## Challenge 03 — CTO Brief

El documento para el board está en [`cto_brief.pdf`](./cto_brief.pdf).

Cubre: modelo de costo del proceso actual, arquitectura explicada para CFO, ROI proyectado con break-even a 12 meses, y el riesgo principal con mitigación concreta.

---

## Challenge 04 — Infraestructura y CI/CD

### Terraform (`infra/`)

Recursos definidos para GCP `us-central1`:

| Recurso | Servicio GCP | Propósito |
|---|---|---|
| API | Cloud Run | Pipeline FastAPI, autoescalable |
| Documentos | GCS bucket | PDFs de clientes |
| Vector store | Cloud SQL PostgreSQL 17 | pgvector para dense search |
| Sparse + Graph | GCE `e2-medium` × 2 | Elasticsearch y FalkorDB (servicios stateful, no Cloud Run) |
| Imágenes | Artifact Registry | Docker images |
| Secrets | Variables de entorno en Cloud Run | Credenciales (ver nota abajo) |

**IAM mínimo:** Service account dedicada con los siguientes roles, todos con scope mínimo necesario:

- `roles/bigquery.dataViewer` y `roles/bigquery.jobUser` — acceso de lectura a BigQuery (project-level)
- `roles/storage.objectViewer` — lectura de documentos desde GCS, con scope limitado al bucket de documentos (bucket-level, no project-level)
- `roles/cloudsql.client` — conexión a Cloud SQL via Auth Proxy (project-level)
- `roles/run.invoker` — invocación del servicio Cloud Run por la misma SA (project-level)

Elasticsearch y FalkorDB corren en GCE y no en Cloud Run porque son servicios stateful que requieren persistencia en disco local. Cloud Run no garantiza filesystem persistente entre instancias. Se usa Container-Optimized OS (COS) porque viene con Docker preinstalado y es la imagen idiomática de GCP para contenedores en GCE.

El acceso directo a Cloud Run queda bloqueado en producción; el tráfico entra por Cloud Load Balancer con Cloud Armor al frente. El hostname de Cloud Run solo responde a identidades autorizadas.

**Concesión:** Las credenciales de Postgres y las API keys van como variables de entorno en Cloud Run, no en Secret Manager. En una implementación productiva real irían a `google_secret_manager_secret` referenciadas con `secretKeyRef`. Se postergó para no agregar un recurso que requiere permisos adicionales y complica el bootstrap sin aportar al diseño arquitectural que se evalúa.

### CI/CD (`.github/workflows/ci.yml`)

Dos branches con comportamiento distinto:

| Branch | Comportamiento |
|---|---|
| `develop` | Tests → build → push a Artifact Registry (sin deploy) |
| `main` | Tests → build → push → deploy a Cloud Run |

El propósito de `develop` es validar que la imagen buildea y los tests pasan antes de mergear a `main`. En un flujo real, `develop` deployaría a un entorno de staging, pero ese entorno se omitió para no agregar complejidad de infra al challenge.

**El pipeline falla si la cobertura de tests cae por debajo del 60%.**

### Observabilidad en producción

| Métrica | Fuente | Cómo |
|---|---|---|
| Latencia p95 del pipeline completo | Langfuse | Traza completa por ejecución; p95 sobre ventana de tiempo |
| Latencia p95 por nodo | Langfuse | Cada nodo instrumentado individualmente |
| Costo por alerta | Langfuse | Tokens de entrada + salida × precio del modelo por nodo |
| Tasa de escalación al humano | Langfuse | Score `escalation_decision` registrado en cada traza |
| Tasa de auto-escalación (score ≥ 9) | Langfuse | Score separado para distinguir escalación por regla vs por LLM |
| Drift del LLM | Langfuse + análisis manual | Distribución de `risk_score` semana a semana; shift en la distribución indica drift. Alert si el promedio se desvía más de 1.5 puntos respecto a la semana anterior |

El dashboard de Langfuse cubre latencia y costo nativamente. La tasa de escalación y el drift se calculan con `scripts/metrics_report.py` (consume la API de Langfuse y produce snapshots JSON, ver `notebooks/metrics_snapshot_*.json`).

---

## Challenge 05 — Incidente PEP

Después de 3 semanas en producción, un auditor externo detecta que el sistema resuelve automáticamente alertas de Personas Políticamente Expuestas (PEPs), cuando la regulación exige escalarlas siempre.

### 1. Detección temprana: qué habría implementado desde el día 1

**Un nodo de revisión post-decisión dentro del grafo.**

El monitoreo externo (Langfuse, dashboards) no es suficiente aquí: si la condición se cumple, no alcanza con reportarlo — hay que corregirlo en el momento, antes de que la decisión se registre como final.

Desde el día 1, el pipeline tendría un nodo adicional al final del grafo que evalúa condiciones de compliance no sujetas a interpretación. Para PEPs: si `customer.is_pep = true` y `decision != escalate_human`, el nodo interrumpe el flujo, revierte la decisión e impone la escalación con `confidence = 1.0`. Este nodo es código puro, sin LLM.

En paralelo, en Langfuse: monitorear la tasa de `decision = dismiss` segmentada por `is_pep`. Si el sistema está descartando alertas de PEPs, ese ratio debería ser 0. Una alerta automática cuando ese ratio > 0 habría detectado el problema en las primeras horas de producción.

### 2. Causa raíz más probable

El sistema puede fallar con PEPs de dos formas:

**Falla RAG:** los chunks recuperados no incluyen la norma que exige escalar PEPs. En ese caso, el LLM no tiene la información necesaria para saber que existe esa obligación.

**Falla LLM:** el RAG recuperó la norma correctamente, pero el LLM la subestimó frente a evidencia contextual fuerte (score de riesgo bajo, historial limpio, monto dentro de umbrales).

La **causa más probable es la segunda**. Los LLMs son estructuralmente malos con restricciones absolutas cuando hay evidencia contextual que apunta en dirección contraria. Un caso con score 2/10 y confianza 0.95 genera una señal fuerte que el modelo tiende a priorizar sobre una obligación regulatoria categórica del tipo "siempre escalar". El modelo está diseñado para ponderar evidencia; una regla sin excepciones rompe esa lógica.

Dicho esto, la distinción no cambia la solución. Mejorar el RAG para que la norma PEP aparezca con mayor score en todos los casos PEP es positivo, pero insuficiente: mientras la decisión final sea del LLM, el riesgo de error no llega a cero.

### 3. Corrección técnica

Tres cambios en el código:

**1. Campo explícito en el estado:**
```python
# graph/state.py
class ComplianceState(TypedDict, total=False):
    ...
    is_pep: bool  # poblado por el Agente Investigador
```

**2. Agente Investigador popula el campo:**
```python
# agents/research.py
state["is_pep"] = customer.get("is_pep", False)
```

**3. Decision Agent evalúa antes de invocar el LLM:**
```python
# agents/decision.py
def run(self, state: ComplianceState) -> ComplianceState:
    if state.get("is_pep"):
        return {
            **state,
            "decision": "escalate_human",
            "confidence": 1.0,
            "applicable_regulations": _get_pep_regulations(state["alert"]["country_code"]),
            "reasoning_steps": [
                "Cliente identificado como Persona Políticamente Expuesta (PEP).",
                "La regulación aplicable exige escalación obligatoria para PEPs sin excepción.",
                "Decisión: escalate_human con confianza 1.0."
            ],
            "decision_status": "done"
        }
    # ... resto del flujo con LLM
```

El LLM no participa en la decisión para PEPs. La lógica está en código, es determinista, es auditable, y es testeable con un test unitario simple.

### 4. Cambio en la arquitectura

La arquitectura es correcta — el aprendizaje afecta al flujo del estado, no a la estructura del grafo.

La tensión de diseño es: ¿la regla PEP vive en el `DecisionAgent` o como edge condicional en el grafo (como ya existe para `risk_score >= 9`)? Se elige en el agente por tres razones:

- Escalar o no es responsabilidad de ese agente; el grafo no debería conocer lógica de negocio
- El flujo del grafo es el mismo para todos los casos; agregar un edge más lo complica sin ganancia
- Este diseño permite que en el futuro exista un agente de decisión por país, con las reglas específicas de cada jurisdicción — en algunos países la restricción PEP tiene matices, y el grafo no necesita saberlo

_**Nota sobre la implementación entregada:** la regla PEP está deliberadamente sujetada al LLM en el código de este challenge para que este incidente pueda ocurrir y responderse. En una implementación real, la condición PEP habría estado en código desde el inicio._

---

## Supuestos

Los siguientes supuestos documentan ambigüedades del escenario que fueron resueltas con criterio propio.

| Supuesto | Impacto |
|---|---|
| **País único por alerta.** Cada alerta refiere a un cliente de un país específico; toda la normativa aplicable es la de ese mismo país. | El RAG filtra por `country_code`; no se combinan regulaciones de distintas jurisdicciones en una misma evaluación |
| **Catálogo de referencias construido manualmente.** Con documentos sintéticos se tiene cobertura completa y se conocen todos los patrones de referencia cruzada. | En producción con documentos reales, el catálogo se construye con un LLM pero es revisado por humanos |
| **Mock de GCS lee del filesystem.** La tool de acceso a documentos lee `fixtures/regulatory_docs/` configurado via `DOCS_DIR` en `.env`. | Cambiar a GCS real requiere implementación menor |
| **Mock de BigQuery lee fixtures JSON.** Los datos de clientes y transacciones viven en `fixtures/customers/*.json`. | Cambiar a BigQuery real requiere implementación menor |
| **LLM de desarrollo no es Vertex AI.** Se usa OpenRouter porque no se requiere cuenta GCP para el desarrollo. En producción el proveedor cambia a Vertex AI con `LLM_PROVIDER=vertexai`. | El código de los agentes no cambia; solo cambian 2 variables de entorno |
| **Regla PEP deliberadamente en el LLM.** La condición PEP no está hardcodeada para que el incidente del Challenge 05 pueda existir. | En una implementación real, la condición estaría en código desde el inicio (ver Challenge 05) |
| **Secret Manager postergado.** Las credenciales van como variables de entorno en Cloud Run. | Concesión conocida; en producción real irían a Secret Manager con `secretKeyRef` |
| **Sin entorno de staging.** El branch `develop` hace build y push pero no despliega. | En un flujo real `develop` deployaría a staging; se omitió para no agregar complejidad de infra al challenge |
| **Evaluaciones RAG fuera del CI/CD.** RAGAS devuelve scores continuos; definir un threshold fijo de fallo es arbitrario. | Las evaluaciones se corren manualmente, de forma periódica o ante cambios en el pipeline |

---

## Mi flujo con AI

Usé Claude como colaborador principal durante todo el desarrollo, en dos modos distintos según la etapa.

**Modo chat (planificación y decisiones):** Todas las decisiones de arquitectura y stack se discutieron en el chat antes de escribir una línea de código. El flujo típico: yo traía el problema o la restricción, discutíamos las opciones (con sus trade-offs, costos, riesgos), y llegábamos a una decisión justificada. El chat también fue útil para buscar riesgos que no había considerado y para ordenar el razonamiento antes de explicarlo en documentación.

**Modo Claude Code (implementación):** Una vez que la decisión estaba tomada, pedía un prompt para Claude Code que describía exactamente qué implementar y con qué restricciones. Llevaba ese prompt a Claude Code, que hacía todos los cambios en los archivos. Los one-liners los escribía yo directamente.

**Debugging híbrido:** Para errores no triviales, el debugging era dirigido por mí, pidiéndole al chat los bloques de código necesarios para hacer la información visible. Dejar la resolución en manos de Claude Code no me resulta efectivo. Mi experiencia me dice mejor por dónde viene el problema y uso la herramienta sólo para generar rápidamente el código necesario.

**Documentos:** El flujo era discutir el contenido en el chat, pedir una redacción general, y corregir manualmente. Ningún documento se usó sin revisión y edición.

**Lo que no delegué:** las decisiones finales de diseño, la revisión de todo el código generado, y el criterio sobre qué vale la pena simplificar vs. qué necesita estar bien hecho.

---

## Conclusión

El proyecto cubre el ciclo completo de un sistema de software en producción: investigación previa al desarrollo (análisis del corpus para definir el chunk size óptimo), stack de desarrollo (Docker Compose, JupyterLab, fixtures, CI/CD, tests, notebooks de smoke test), stack de producción (herramientas de datos, RAG híbrido, agentes, API, observabilidad, infraestructura como código), herramientas de evaluación (generación de dataset y métricas de calidad del retriever), y documentación técnica y ejecutiva.

Cada decisión de stack tiene una justificación explícita: costo, operabilidad, compatibilidad con la infraestructura existente, o restricciones del entorno de producción. Donde hubo concesiones, están documentadas con su razonamiento.

La solución no pierde de vista que el problema es de negocio: un proceso que cuesta tiempo y dinero, con un riesgo regulatorio real, y un board que necesita confiar en los números antes de aprobar un presupuesto. El sistema técnico y el documento para el CTO responden a la misma pregunta desde ángulos distintos.
