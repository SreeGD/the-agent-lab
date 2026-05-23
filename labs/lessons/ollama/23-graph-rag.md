# 23 — GraphRAG (Session 12)

> **Provider variant — Ollama (`llama3.2`)** This is the Ollama version of this lesson. The logic, patterns, and exercises are identical to the Anthropic version. What differs: import is `langchain_ollama.ChatOllama`, model is `llama3.2`, no API key is needed (Ollama runs locally), and `ollama serve` must be running. Code file: `labs/ollama/23_graph_rag_ollama.py`.

> **Answers live in relationships.** Extract entities + relationships from your corpus into a knowledge graph; at query time, traverse the graph instead of (or alongside) retrieving chunks. The right pattern when answers span multiple chunks — multi-hop reasoning, relationship queries, "who at X worked on Y" type questions.

---

## Roadmap — where this lesson sits in the journey

```
═══════ PHASE 1: FOUNDATION (done) ═══════                ═══════ PHASE 2 ═══════

  ✓ 01-12 (foundation)                                     Tracks A/B/C/D/E: ✓ all done
                                                           Track E.5: RAG Architectures
                                                             ✓ Session 11: Hybrid RAG
                                                             ▶ Session 12: GRAPHRAG  ◄ HERE
                                                             ○ Session 13: Corrective RAG
                                                           Track F: ○ Production
```

**Why this lesson now:** Sessions 9 + 11 covered chunk-based RAG (dense / sparse / hybrid). All three retrieve **chunks**. For questions whose answers span multiple chunks, you need a different shape entirely — a graph.

---

## File involved

| File | Role |
|---|---|
| [`23_graph_rag_ollama.py`](../ollama/23_graph_rag_ollama.py) | Extract a knowledge graph from a small focused corpus, build it in NetworkX, run four query demos (list entities by type, 1-hop neighbors, shortest path between two entities, multi-hop QA with subgraph-as-context). |

---

## What problem it solves

Classical RAG (Sessions 9 + 11) retrieves the chunks **most similar** to your query. That works great when the answer is **in one chunk**.

It fails when the answer requires **connecting facts across chunks**:

- *"Who at the AgenticCourse project worked on the model the repo uses?"* — requires hopping: AgenticCourse → model → provider, plus a person from that team. No single chunk has the full chain.
- *"Which other products work with MCP?"* — requires aggregating across chunks
- *"How is X different from Y?"* — requires comparing entity attributes pulled from different chunks
- *"What's the dependency tree of project Z?"* — graph-shaped data, retrieved poorly by similarity search

GraphRAG turns the corpus into a **knowledge graph**. Nodes are entities (people, orgs, products, concepts). Edges are relationships. Queries become **graph traversals** + targeted text retrieval.

---

## The analogy

**A directory service vs. a search engine.**

Classical RAG is a search engine — type words, get back the most-similar pages.

GraphRAG is a directory service — *"who reports to whom; who works on what project; who lives in Seattle."* You can answer questions search engines fail at: *"who at Microsoft works on the LangGraph competitor?"* — that's three hops (Microsoft → employees → projects → which-project) over structured relationships.

Real production stacks use both. Search is fine for "what did the company announce?" — directory is right for "who in Engineering owns the API gateway?"

---

## Visual

```
   raw text chunks
        │
        ▼
   ┌─────────────────────────────┐
   │ Entity extraction (LLM)     │   Pydantic models:
   │                              │   - Entity (name, type, description)
   │ model.with_structured_output │   - Relationship (source, target, label)
   │   (KnowledgeGraph)           │   - KnowledgeGraph (entities, relationships)
   └────────┬────────────────────┘
            │
            ▼
   ┌─────────────────────────────┐
   │ NetworkX (or Neo4j) graph    │   nodes = entities
   │                              │   edges = labeled relationships
   └────────┬────────────────────┘
            │
            ▼
   ┌─────────────────────────────┐
   │ Query-time retrieval:        │
   │  1. Find seed entities        │   via name match or embedding similarity
   │  2. Traverse the graph        │   BFS / DFS / shortest_path / community
   │  3. Return relevant subgraph  │   triples + linked chunks
   │  4. Feed to LLM as context    │   for synthesis
   └─────────────────────────────┘
```

---

## Concept — entity extraction

```python
from langchain_ollama import ChatOllama
from typing import Literal
from pydantic import BaseModel, Field

# Ollama runs locally — no API key needed.
model = ChatOllama(model="llama3.2", temperature=0)

class Entity(BaseModel):
    name: str = Field(description="Canonical name, e.g. 'AgenticCourse'")
    type: Literal["person", "organization", "product", "concept", "location"]
    description: str = Field(description="One-sentence summary")

class Relationship(BaseModel):
    source: str   # must match an Entity.name above
    target: str
    label: str    # snake_case verb: 'works_on', 'built_by', 'uses', ...

class KnowledgeGraph(BaseModel):
    entities: list[Entity]
    relationships: list[Relationship]

extractor = model.with_structured_output(KnowledgeGraph)
kg = extractor.invoke(corpus_text)
# kg.entities, kg.relationships
```

**Pydantic enforces the contract.** The LLM cannot return a relationship pointing at an entity it didn't list (the response would fail validation). The extractor's job is just to produce a well-formed `KnowledgeGraph` from prose.

---

## Concept — building the graph

```python
import networkx as nx

g = nx.DiGraph()
for ent in kg.entities:
    g.add_node(ent.name, type=ent.type, description=ent.description)
for rel in kg.relationships:
    if rel.source in g.nodes and rel.target in g.nodes:
        g.add_edge(rel.source, rel.target, label=rel.label)
```

NetworkX is in-memory and pure Python — perfect for dev. Production swaps to Neo4j / Memgraph / Kuzu (same graph queries, different storage). The query patterns translate directly.

---

## Concept — multi-hop QA

The killer pattern:

```python
def extract_subgraph_context(g, seed_entities, depth=2):
    """Return text serialization of triples within `depth` hops of seeds."""
    nodes = set(seed_entities)
    frontier = set(seed_entities)
    for _ in range(depth):
        frontier = {neighbor
                    for n in frontier
                    for neighbor in (set(g.successors(n)) | set(g.predecessors(n)))}
        nodes |= frontier
    return "\n".join(
        f"  {a} --[{attrs['label']}]--> {b}"
        for a, b, attrs in g.edges(data=True)
        if a in nodes and b in nodes
    )

subgraph_text = extract_subgraph_context(g, seed_entities=["AgenticCourse"], depth=2)
response = model.invoke([
    SystemMessage("Answer using ONLY the relationships in the graph context. Cite each."),
    HumanMessage(f"Graph:\n{subgraph_text}\n\nQuestion: {question}"),
])
```

The LLM sees **structured triples**, not unstructured prose. It can chain the relationships exactly because the graph makes the chain explicit.

---

## Run it

**Prerequisites:** `ollama serve` must be running locally, and `ollama pull llama3.2` must have been run first.

```bash
python ollama/23_graph_rag_ollama.py
```

---

## Walk-through — when to use GraphRAG

### Use GraphRAG when

- **Multi-hop questions are common** — "X built what Y uses to do Z"
- **Your domain has clear entities + relationships** — orgs, products, people, concepts, drug-target interactions, legal precedents
- **Relationships matter as much as content** — org charts, dependency graphs, citation networks, supply chains
- **You need explainable answers** — graph traversal IS an audit trail; classical RAG's "we retrieved these chunks" is fuzzier

### Stick with classical / hybrid RAG when

- Single-fact retrieval is enough ("what does our policy say about X?")
- The corpus is mostly unstructured prose with few well-defined entities
- You can't build a clean entity vocabulary (anything goes)
- Cost is the dominant constraint (entity extraction adds LLM calls)

### Use BOTH (hybrid + graph) when

You want the structured precision of graph traversal AND the supporting prose for the final answer. Production pattern: retrieve subgraph from graph, retrieve relevant chunks from vector store, feed BOTH to the answer LLM.

---

## Production patterns this unlocks

| Pattern | Use case |
|---|---|
| **Org chart QA** | "who reports to whom across teams" — directly graph-shaped |
| **Legal precedent** | Case → cites → case → cites... — multi-hop reasoning over a citation graph |
| **Biomedical** | Drug → targets → protein → involved_in → disease — gold standard for GraphRAG |
| **Customer support** | Product → has_feature → feature → depends_on → dependency — debugging "why doesn't X work" |
| **Compliance audits** | Policy → applies_to → entity → owned_by → person → reports_to → manager — traceable accountability |
| **Knowledge management** | Internal wikis with topic relationships, project ownership, decision rationale |

---

## Try this

1. **Replace the corpus** with your own internal docs (or a subset of `LEARNINGS.md`). Watch what entities + relationships the LLM extracts. Tune the system prompt to bias toward your domain vocabulary.
2. **Multi-hop your own question** — pick two entities in your graph that aren't directly connected. Run `nx.shortest_path()`. Trace the path manually.
3. **Combine with `09_rag.py`** — for each query, retrieve top-3 chunks (classical) AND retrieve a 2-hop subgraph (this lesson). Feed both to the answer LLM. Compare quality vs either alone.
4. **Swap NetworkX for Neo4j** — install the `neo4j` Python driver, replace the `nx.DiGraph` with Cypher `CREATE` statements. The query logic is the same; just different storage.
5. **Add entity deduplication** — after extraction, embed entity names and merge any pair with cosine > 0.9. Prevents `AgenticCourse` and `AgenticCourse project` from being separate nodes.

---

## Mental model in one line

> **GraphRAG turns your corpus into a queryable knowledge graph. Multi-hop questions that classical RAG fumbles ('who at X built what Y uses?') become exact graph traversals. The LLM extracts the graph once; queries are cheap thereafter. Use it when relationships matter as much as content.**

---

## FAQ

**Q: Does GraphRAG replace classical RAG?**

A: No — they complement each other. GraphRAG answers structural questions ("how are X and Y connected?"); classical RAG answers content questions ("what does the doc say about X?"). Production stacks usually do both, feeding the answer LLM both a subgraph and relevant chunks.

**Q: How does entity extraction handle ambiguity?**

A: The system prompt biases the LLM toward canonical names. For production: post-process to dedupe (string similarity, embedding clustering) and to normalize types.

**Q: What's the cost of extraction?**

A: One LLM call per chunk (or per document). For a corpus of 1000 chunks at ~500 tokens each, you're looking at significant local inference time with Ollama. The extraction runs once (offline); queries are cheap. Re-run only when docs change.

**Q: How big can the graph be?**

A: NetworkX handles ~1M nodes comfortably in memory. Beyond that → Neo4j, Memgraph, Kuzu. Cypher queries scale to hundreds of millions of nodes on appropriate hardware.

**Q: How does this compare to Microsoft's full GraphRAG?**

A: Microsoft's paper adds community detection (Leiden algorithm), hierarchical community summaries, and global/local query routing. This lesson covers the foundation; community detection is its own follow-up. For most use cases, plain extract + traverse (this lesson) is enough.

**Q: Can I extract from PDFs?**

A: Yes — combine with Session 9 (Files & Document AI). Extract text from the PDF first, then pass to the LLM to extract a `KnowledgeGraph`. Same Pydantic schema; the only difference is the input type.

**Q: How do I handle edge cases the LLM extraction misses?**

A: Two strategies: (1) **Validate then retry** — if Pydantic validation fails, re-prompt with the error. (2) **Manual editing** — for high-stakes graphs, a human reviews and corrects extracted entities/relationships before committing to the production store.

**Q: What about temporal relationships?**

A: Add a `valid_from` / `valid_to` to your Relationship schema. The graph then represents time-varying facts. Queries can filter by time. Production-only concern; out of scope for this demo.

**Q: Is there a LangChain-native GraphRAG?**

A: `langchain-experimental` has `LLMGraphTransformer` for extraction and `Neo4jGraph` for storage. They're useful starting points. The pattern in this lesson is hand-rolled for clarity — once you understand it, the LangChain wrappers are easy to adopt.

---

## Related

- **Previous:** [22 — Hybrid RAG](22-hybrid-rag.md)
- **Next:** Session 13 — Corrective RAG (Track E.5 finale)
- **Builds on:** [09 — RAG](09-rag.md), [05 — Structured output](05-structured-output.md) (the extraction relies on `with_structured_output`)
- **Skill it lives under:** [`labs/skills/agenticcourse-rag/SKILL.md`](../skills/agenticcourse-rag/SKILL.md) — GraphRAG is listed as a variant; this lesson is the deep dive
- **Curriculum tracker:** [`../CURRICULUM.md`](../CURRICULUM.md) — Session 12 of 40 (Track E.5 2/3)
