"""GraphRAG — answers live in relationships.

Extract entities + relationships from text via with_structured_output,
build a NetworkX knowledge graph, then answer questions by traversing
the graph (instead of, or alongside, retrieving chunks).

Best for multi-hop questions that classical RAG struggles with:
  "Which company built the model that the AgenticCourse repo uses?"
This requires connecting: AgenticCourse → uses → Claude → built_by → Anthropic.
Classical RAG would need all three facts in one chunk; the graph traversal
is exact.

Demos:
  1. List all extracted entities by type
  2. Show 1-hop neighbors of a chosen entity
  3. Find shortest path between two entities (multi-hop traversal)
  4. Multi-hop QA: extract subgraph → feed to LLM as structured context
"""

from typing import Literal

import networkx as nx
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "claude-sonnet-4-6"
model = ChatAnthropic(model=MODEL, temperature=0)


# =====================================================================
# Demo corpus — small, clean, multiple connected entities
# =====================================================================

CORPUS = """\
Sree Mallipeddi is a senior data scientist exploring agentic AI. He maintains the AgenticCourse repository, a public learning project on GitHub that walks through building agentic systems incrementally.

AgenticCourse uses LangChain for composition and LangGraph for stateful workflows. The default model in every lab is Anthropic's Claude Sonnet 4.6. LangChain itself is an open-source framework released by LangChain Inc. LangGraph is a sister project also from LangChain Inc.

Claude is the LLM family built by Anthropic. Anthropic is an AI safety company headquartered in San Francisco; they also publish the Claude Agent SDK and the Model Context Protocol (MCP) specification. MCP is implemented by AgenticCourse's mcp_server.py and consumed by its mcp_client.py. MCP servers are also used by Claude Desktop, the GUI app for Claude.

For embeddings, AgenticCourse uses sentence-transformers/all-MiniLM-L6-v2, a local open-source model from the sentence-transformers library originally from UKP Lab at TU Darmstadt.
"""


# =====================================================================
# Typed extraction schema
# =====================================================================

class Entity(BaseModel):
    """A real-world entity mentioned in the text."""
    name: str = Field(description="Canonical name, e.g. 'Anthropic', 'Sree Mallipeddi', 'LangChain'.")
    type: Literal["person", "organization", "product", "concept", "location"]
    description: str = Field(description="One-sentence summary of this entity, drawn from the text.")


class Relationship(BaseModel):
    """A directed relationship between two entities."""
    source: str = Field(description="Source entity name (must exactly match an Entity.name).")
    target: str = Field(description="Target entity name (must exactly match an Entity.name).")
    label: str = Field(
        description="Verb-like relationship label using snake_case, e.g. 'works_on', "
                    "'built_by', 'uses', 'employs', 'headquartered_in', 'publishes'.",
    )


class KnowledgeGraph(BaseModel):
    """All entities and relationships extracted from a text."""
    entities: list[Entity]
    relationships: list[Relationship]


# =====================================================================
# Extract a knowledge graph from text
# =====================================================================

def extract_graph(text: str) -> KnowledgeGraph:
    extractor = model.with_structured_output(KnowledgeGraph)
    result = extractor.invoke([
        SystemMessage(
            "Extract every entity and relationship from the text. "
            "Use canonical names (no duplicates). For each relationship, "
            "source and target MUST be entity names you listed. "
            "Aim for 8-15 entities and 12-20 relationships from a paragraph."
        ),
        HumanMessage(text),
    ])
    return result


def build_networkx_graph(kg: KnowledgeGraph) -> nx.DiGraph:
    g = nx.DiGraph()
    for ent in kg.entities:
        g.add_node(ent.name, type=ent.type, description=ent.description)
    for rel in kg.relationships:
        # Be defensive — sometimes the LLM emits a relationship pointing at an
        # entity it didn't list. We drop those rather than create stub nodes.
        if rel.source in g.nodes and rel.target in g.nodes:
            g.add_edge(rel.source, rel.target, label=rel.label)
    return g


# =====================================================================
# Demos
# =====================================================================

def demo_list_entities(g: nx.DiGraph, kg: KnowledgeGraph) -> None:
    print("\n" + "=" * 70)
    print(f"DEMO 1 — All entities by type ({len(g.nodes)} total)")
    print("=" * 70)
    by_type: dict[str, list] = {}
    for node, attrs in g.nodes(data=True):
        by_type.setdefault(attrs.get("type", "unknown"), []).append((node, attrs.get("description", "")))
    for type_, items in sorted(by_type.items()):
        print(f"\n  {type_.upper()}:")
        for name, desc in items:
            print(f"    • {name}")
            print(f"        {desc[:90]}{'...' if len(desc) > 90 else ''}")


def demo_neighbors(g: nx.DiGraph, entity: str) -> None:
    print("\n" + "=" * 70)
    print(f"DEMO 2 — 1-hop neighbors of {entity!r}")
    print("=" * 70)
    if entity not in g.nodes:
        print(f"  ! {entity!r} not in graph")
        return

    print(f"\n  Outgoing from {entity!r}:")
    for target in g.successors(entity):
        label = g.edges[entity, target].get("label", "?")
        print(f"    {entity} --[{label}]--> {target}")

    print(f"\n  Incoming to {entity!r}:")
    for source in g.predecessors(entity):
        label = g.edges[source, entity].get("label", "?")
        print(f"    {source} --[{label}]--> {entity}")


def demo_shortest_path(g: nx.DiGraph, source: str, target: str) -> None:
    print("\n" + "=" * 70)
    print(f"DEMO 3 — shortest path: {source!r} → {target!r}")
    print("=" * 70)
    # We use the undirected version for path-finding (a path in either direction counts)
    undirected = g.to_undirected()
    try:
        path = nx.shortest_path(undirected, source=source, target=target)
    except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
        print(f"  ! {e}")
        return

    print(f"\n  found {len(path) - 1}-hop path:")
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        # Use whichever edge direction exists
        if g.has_edge(a, b):
            label = g.edges[a, b].get("label", "?")
            print(f"    {a} --[{label}]--> {b}")
        elif g.has_edge(b, a):
            label = g.edges[b, a].get("label", "?")
            print(f"    {a} <--[{label}]-- {b}")
        else:
            print(f"    {a} -- ? -- {b}")


def extract_subgraph_context(g: nx.DiGraph, seed_entities: list[str], depth: int = 2) -> str:
    """Return a text serialization of all triples within `depth` hops of seeds."""
    nodes_to_include = set()
    frontier = set(e for e in seed_entities if e in g.nodes)
    nodes_to_include |= frontier
    for _ in range(depth):
        new_frontier = set()
        for n in frontier:
            new_frontier |= set(g.successors(n)) | set(g.predecessors(n))
        frontier = new_frontier - nodes_to_include
        nodes_to_include |= frontier

    triples = []
    for a, b, attrs in g.edges(data=True):
        if a in nodes_to_include and b in nodes_to_include:
            triples.append(f"  {a} --[{attrs.get('label', '?')}]--> {b}")

    return "\n".join(triples)


def demo_multi_hop_qa(g: nx.DiGraph, question: str, seeds: list[str]) -> None:
    print("\n" + "=" * 70)
    print(f"DEMO 4 — Multi-hop QA via subgraph retrieval")
    print("=" * 70)
    print(f"  question: {question}")
    print(f"  seed entities: {seeds}")

    subgraph_text = extract_subgraph_context(g, seeds, depth=2)
    print(f"\n  retrieved subgraph ({subgraph_text.count(chr(10)) + 1} triples):")
    print(subgraph_text)

    print("\n  feeding subgraph to model as structured context...")
    response = model.invoke([
        SystemMessage(
            "Answer the user's question using ONLY the relationships shown in "
            "the knowledge graph context. Cite each relationship you use. If "
            "the graph doesn't support the answer, say so."
        ),
        HumanMessage(f"Knowledge graph relationships:\n{subgraph_text}\n\nQuestion: {question}"),
    ])
    print(f"\n  answer: {response.content}")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("GraphRAG — answers live in relationships")
    print("=" * 70)
    print(f"  corpus: {len(CORPUS)} chars / {CORPUS.count('.')} sentences")

    print("\n  extracting entities + relationships via with_structured_output...")
    kg = extract_graph(CORPUS)
    print(f"  extracted {len(kg.entities)} entities, {len(kg.relationships)} relationships")

    g = build_networkx_graph(kg)
    print(f"  built graph: {len(g.nodes)} nodes, {len(g.edges)} edges")

    demo_list_entities(g, kg)
    demo_neighbors(g, "Claude")
    demo_shortest_path(g, "Sree Mallipeddi", "Anthropic")
    demo_multi_hop_qa(
        g,
        question="Which company built the model that the AgenticCourse repo uses by default?",
        seeds=["AgenticCourse"],
    )

    print("\n" + "=" * 70)
    print("WHAT JUST HAPPENED")
    print("=" * 70)
    print(
        "  • A single LLM call extracted a typed KnowledgeGraph (Pydantic) from\n"
        "    the corpus — entities with types + descriptions, relationships with\n"
        "    source/target/label.\n"
        "  • NetworkX held the graph in memory. Same queries work in Neo4j / Memgraph\n"
        "    / Kuzu with cypher; NetworkX is the dev-time stand-in.\n"
        "  • Multi-hop QA (Demo 4) is the killer use case: 'which company built the\n"
        "    model that this repo uses?' requires connecting facts across what would\n"
        "    be separate chunks in classical RAG. Graph traversal is exact.\n"
        "  • In production: combine graph retrieval with classical chunk retrieval —\n"
        "    feed BOTH to the answer LLM. The graph gives structure; the chunks give\n"
        "    the supporting prose.\n"
        "  • Microsoft's full GraphRAG paper adds community detection (Leiden algo)\n"
        "    and hierarchical summaries on top — a follow-up worth its own session."
    )
