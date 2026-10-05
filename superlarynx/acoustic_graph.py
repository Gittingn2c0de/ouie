"""Superlarynx Acoustic/Event Graph — Prompt 3.

An intermediate representation between causal hypothesis and DSP.
The graph supports nodes for events, stimuli, objects, materials, bodies,
excitations, resonators, interactions, motions, environments, propagation,
listeners, modulation, and secondary/tertiary events.

Connections represent causality, energy transfer, modulation, containment,
propagation, resonance, or temporal dependency.

The acoustic compiler translates this graph into actual DSP processes.
Materials are NOT hardcoded waveforms — they are parameter distributions
and state variables.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    AcousticEvent, Distribution, Environment, ListenerState,
    MaterialState, ObjectState, PhysicsMode, Stimulus,
)


# ---------------------------------------------------------------------------
# Graph Node Types (Prompt 3)
# ---------------------------------------------------------------------------

class NodeType(Enum):
    EVENT = "event"
    STIMULUS = "stimulus"
    OBJECT = "object"
    MATERIAL = "material"
    BODY = "body"
    EXCITATION = "excitation"
    RESONATOR = "resonator"
    INTERACTION = "interaction"
    MOTION = "motion"
    ENVIRONMENT = "environment"
    PROPAGATION = "propagation"
    LISTENER = "listener"
    MODULATION = "modulation"
    SECONDARY_EVENT = "secondary_event"
    TERTIARY_EVENT = "tertiary_event"


class EdgeType(Enum):
    """Connection types between nodes."""
    CAUSALITY = "causality"             # A causes B or enables B
    ENERGY_TRANSFER = "energy_transfer" # Energy flows from A into B
    INTERACTION = "interaction"         # A physically interacts with B
    MODULATION = "modulation"           # A modulates a parameter/state of B
    CONTAINMENT = "containment"         # A contains B
    PROPAGATION = "propagation"         # Acoustic/physical energy travels through A to B
    RESONANCE = "resonance"             # A excites or couples into B's resonant behavior
    TEMPORAL = "temporal"               # A precedes B in time


# ---------------------------------------------------------------------------
# Graph Nodes
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    """A node in the acoustic/event graph."""
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    node_type: NodeType = NodeType.EVENT
    label: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    # Typed payloads — only one is populated depending on node_type
    event: Optional[AcousticEvent] = None
    stimulus: Optional[Stimulus] = None
    object_state: Optional[ObjectState] = None
    material: Optional[MaterialState] = None
    environment: Optional[Environment] = None
    listener: Optional[ListenerState] = None
    # For DSP compilation
    mechanism: str = ""           # high-level mechanism name (Prompt 19)
    dsp_params: Dict[str, Any] = field(default_factory=dict)
    # Timing
    start_time: float = 0.0
    duration: Optional[float] = None


@dataclass
class GraphEdge:
    """A directed edge in the acoustic/event graph."""
    edge_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    source_id: str = ""
    target_id: str = ""
    edge_type: EdgeType = EdgeType.CAUSALITY
    weight: float = 1.0           # energy/influence weight
    delay: float = 0.0            # propagation delay in seconds
    parameters: Dict[str, Any] = field(default_factory=dict)
    label: str = ""


# ---------------------------------------------------------------------------
# The Acoustic Graph
# ---------------------------------------------------------------------------

@dataclass
class AcousticGraph:
    """The intermediate acoustic/event graph (Prompt 3).

    Example flow:
        MARBLE → rolling → acceleration → collision with granite →
        contact impulse → marble vibration → granite modal excitation →
        surface micro-fracture/scrape → room reflections → listener

    The acoustic compiler translates this into DSP processes.
    Materials are parameter distributions, NOT hardcoded waveforms.
    """
    graph_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- Mutation methods --

    def add_node(self, node: GraphNode) -> str:
        """Add a node to the graph, return its ID."""
        self.nodes[node.node_id] = node
        return node.node_id

    def add_edge(self, source_id: str, target_id: str,
                 edge_type: EdgeType = EdgeType.CAUSALITY,
                 weight: float = 1.0, delay: float = 0.0,
                 label: str = "", **params) -> str:
        """Add a directed edge between two nodes."""
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            delay=delay,
            label=label,
            parameters=params,
        )
        self.edges.append(edge)
        return edge.edge_id

    def connect_chain(self, node_ids: List[str],
                      edge_type: EdgeType = EdgeType.CAUSALITY) -> None:
        """Connect a list of nodes in sequence (A→B→C→...)."""
        for i in range(len(node_ids) - 1):
            self.add_edge(node_ids[i], node_ids[i + 1], edge_type)

    # -- Query methods --

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self.nodes.get(node_id)

    def get_successors(self, node_id: str) -> List[GraphNode]:
        """Get all nodes that this node feeds into."""
        target_ids = [e.target_id for e in self.edges if e.source_id == node_id]
        return [self.nodes[tid] for tid in target_ids if tid in self.nodes]

    def get_predecessors(self, node_id: str) -> List[GraphNode]:
        """Get all nodes that feed into this node."""
        source_ids = [e.source_id for e in self.edges if e.target_id == node_id]
        return [self.nodes[sid] for sid in source_ids if sid in self.nodes]

    def get_roots(self) -> List[GraphNode]:
        """Get nodes with no incoming edges (stimuli, initial events)."""
        targets = {e.target_id for e in self.edges}
        return [n for nid, n in self.nodes.items() if nid not in targets]

    def get_leaves(self) -> List[GraphNode]:
        """Get nodes with no outgoing edges (listener, final signals)."""
        sources = {e.source_id for e in self.edges}
        return [n for nid, n in self.nodes.items() if nid not in sources]

    def topological_order(self) -> List[GraphNode]:
        """Return nodes in topological (causal) order for compilation."""
        in_degree = {nid: 0 for nid in self.nodes}
        for edge in self.edges:
            if edge.target_id in in_degree:
                in_degree[edge.target_id] += 1
        queue = [nid for nid, d in in_degree.items() if d == 0]
        order = []
        while queue:
            nid = queue.pop(0)
            order.append(self.nodes[nid])
            for edge in self.edges:
                if edge.source_id == nid and edge.target_id in in_degree:
                    in_degree[edge.target_id] -= 1
                    if in_degree[edge.target_id] == 0:
                        queue.append(edge.target_id)
        return order

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the graph for LLM consumption / JSON transport."""
        return {
            "graph_id": self.graph_id,
            "physics_mode": self.physics_mode.value,
            "nodes": [
                {
                    "id": n.node_id,
                    "type": n.node_type.value,
                    "label": n.label,
                    "mechanism": n.mechanism,
                    "start_time": n.start_time,
                    "duration": n.duration,
                    "parameters": n.parameters,
                    "dsp_params": n.dsp_params,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "id": e.edge_id,
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": e.edge_type.value,
                    "weight": e.weight,
                    "delay": e.delay,
                    "label": e.label,
                }
                for e in self.edges
            ],
        }

    @classmethod
    def validate_dict(cls, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate graph schema before compilation."""
        errors = []
        
        # Check nodes
        valid_nodes = {n.value for n in NodeType}
        for nd in data.get("nodes", []):
            if nd.get("type") not in valid_nodes:
                errors.append({
                    "type": "GRAPH_VALIDATION_ERROR",
                    "reason": "Invalid NodeType",
                    "node_id": nd.get("id"),
                    "invalid_type": nd.get("type"),
                })

        # Check edges
        valid_edges = {e.value for e in EdgeType}
        for ed in data.get("edges", []):
            edge_type_val = ed.get("type", "causality")
            if edge_type_val not in valid_edges:
                errors.append({
                    "type": "GRAPH_VALIDATION_ERROR",
                    "reason": "EdgeType is not registered",
                    "edge": {
                        "source": ed.get("source"),
                        "target": ed.get("target"),
                        "type": edge_type_val
                    },
                    "producer": "Storyteller -> Causal Hypothesis -> Graph Builder"
                })
        return errors

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AcousticGraph":
        """Reconstruct a graph from its serialized form."""
        graph = cls(
            graph_id=data.get("graph_id", ""),
            physics_mode=PhysicsMode(data.get("physics_mode", "plausible")),
            metadata=data.get("metadata", {})
        )
        for nd in data.get("nodes", []):
            node = GraphNode(
                node_id=nd["id"],
                node_type=NodeType(nd["type"]),
                label=nd.get("label", ""),
                mechanism=nd.get("mechanism", ""),
                start_time=nd.get("start_time", 0.0),
                duration=nd.get("duration"),
                parameters=nd.get("parameters", {}),
                dsp_params=nd.get("dsp_params", {}),
            )
            # Hydrate material if present (assuming material is passed in params for now, 
            # though schema says it might be under 'material')
            if "material" in nd and nd["material"]:
                from .models import MaterialState
                node.material = MaterialState(**nd["material"])
                
            graph.nodes[node.node_id] = node
        for ed in data.get("edges", []):
            edge = GraphEdge(
                edge_id=ed.get("id", ""),
                source_id=ed["source"],
                target_id=ed["target"],
                edge_type=EdgeType(ed.get("type", "causality")),
                weight=ed.get("weight", 1.0),
                delay=ed.get("delay", 0.0),
                label=ed.get("label", ""),
            )
            graph.edges.append(edge)
        return graph


# ---------------------------------------------------------------------------
# Graph Builder Helpers
# ---------------------------------------------------------------------------

def build_impact_graph(
    striker: ObjectState,
    target: ObjectState,
    environment: Environment,
    listener: ListenerState,
    physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE,
) -> AcousticGraph:
    """Build a prototypical impact event graph.

    Example: marble hitting rock.
    MARBLE → motion → collision → contact impulse → striker vibration →
    target modal excitation → surface micro-events → room reflections → listener
    """
    g = AcousticGraph(physics_mode=physics_mode)

    # Nodes
    n_striker = g.add_node(GraphNode(
        node_type=NodeType.OBJECT, label=striker.name or "striker",
        object_state=striker,
    ))
    n_motion = g.add_node(GraphNode(
        node_type=NodeType.MOTION, label="approach",
        parameters={"velocity": striker.velocity},
    ))
    n_interaction = g.add_node(GraphNode(
        node_type=NodeType.INTERACTION, label="collision",
        mechanism="COLLISION",
        parameters={
            "impact_velocity": striker.velocity,
        },
    ))
    n_excitation = g.add_node(GraphNode(
        node_type=NodeType.EXCITATION, label="contact impulse",
        mechanism="IMPULSE",
    ))
    n_striker_res = g.add_node(GraphNode(
        node_type=NodeType.RESONATOR,
        label=f"{striker.name or 'striker'} vibration",
        mechanism="MODAL_RESPONSE",
        material=striker.material,
    ))
    n_target = g.add_node(GraphNode(
        node_type=NodeType.OBJECT, label=target.name or "target",
        object_state=target,
    ))
    n_target_res = g.add_node(GraphNode(
        node_type=NodeType.RESONATOR,
        label=f"{target.name or 'target'} modal excitation",
        mechanism="MODAL_RESPONSE",
        material=target.material,
    ))
    n_env = g.add_node(GraphNode(
        node_type=NodeType.ENVIRONMENT, label=environment.name or "room",
        environment=environment,
        mechanism="ENVIRONMENTAL_REFLECTION",
    ))
    n_prop = g.add_node(GraphNode(
        node_type=NodeType.PROPAGATION, label="propagation",
        mechanism="ENVIRONMENTAL_REFLECTION",
    ))
    n_listener = g.add_node(GraphNode(
        node_type=NodeType.LISTENER, label="listener",
        listener=listener,
    ))

    # Causal chain
    g.connect_chain([
        n_striker, n_motion, n_interaction, n_excitation,
    ])
    # Excitation feeds both resonators
    g.add_edge(n_excitation, n_striker_res, EdgeType.ENERGY_TRANSFER)
    g.add_edge(n_excitation, n_target_res, EdgeType.ENERGY_TRANSFER)
    g.add_edge(n_target, n_target_res, EdgeType.RESONANCE)
    # Both resonators feed into environment
    g.add_edge(n_striker_res, n_env, EdgeType.PROPAGATION)
    g.add_edge(n_target_res, n_env, EdgeType.PROPAGATION)
    # Environment to listener
    g.connect_chain([n_env, n_prop, n_listener])

    return g


def build_friction_graph(
    moving_object: ObjectState,
    surface: ObjectState,
    environment: Environment,
    listener: ListenerState,
    physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE,
) -> AcousticGraph:
    """Build a prototypical friction/scrape event graph."""
    g = AcousticGraph(physics_mode=physics_mode)

    n_obj = g.add_node(GraphNode(
        node_type=NodeType.OBJECT, label=moving_object.name or "moving object",
        object_state=moving_object,
    ))
    n_surface = g.add_node(GraphNode(
        node_type=NodeType.OBJECT, label=surface.name or "surface",
        object_state=surface,
    ))
    n_motion = g.add_node(GraphNode(
        node_type=NodeType.MOTION, label="sliding motion",
        mechanism="FRICTION",
    ))
    n_contact = g.add_node(GraphNode(
        node_type=NodeType.INTERACTION, label="surface contact",
        mechanism="CONTACT",
    ))
    n_scrape = g.add_node(GraphNode(
        node_type=NodeType.EXCITATION, label="scrape excitation",
        mechanism="SCRAPE",
    ))
    n_obj_res = g.add_node(GraphNode(
        node_type=NodeType.RESONATOR,
        label=f"{moving_object.name or 'object'} resonance",
        mechanism="MODAL_RESPONSE",
        material=moving_object.material,
    ))
    n_surface_res = g.add_node(GraphNode(
        node_type=NodeType.RESONATOR,
        label=f"{surface.name or 'surface'} resonance",
        mechanism="MODAL_RESPONSE",
        material=surface.material,
    ))
    n_env = g.add_node(GraphNode(
        node_type=NodeType.ENVIRONMENT, label=environment.name or "room",
        environment=environment,
        mechanism="ENVIRONMENTAL_REFLECTION",
    ))
    n_listener = g.add_node(GraphNode(
        node_type=NodeType.LISTENER, label="listener",
        listener=listener,
    ))

    g.connect_chain([n_obj, n_motion, n_contact, n_scrape])
    g.add_edge(n_surface, n_contact, EdgeType.CAUSALITY)
    g.add_edge(n_scrape, n_obj_res, EdgeType.ENERGY_TRANSFER)
    g.add_edge(n_scrape, n_surface_res, EdgeType.ENERGY_TRANSFER)
    g.add_edge(n_obj_res, n_env, EdgeType.PROPAGATION)
    g.add_edge(n_surface_res, n_env, EdgeType.PROPAGATION)
    g.add_edge(n_env, n_listener, EdgeType.PROPAGATION)

    return g
