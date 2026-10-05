"""Superlarynx Acoustic Compiler — Prompt 3, 19, 25.

Translates an AcousticGraph into a concrete DSP recipe that the
existing Web Audio renderer can execute.

The compiler walks the graph in topological (causal) order, compiling
each node's mechanism into DSP layers, accumulating delays from edges,
and merging the result into a single recipe JSON.

This is the bridge between the causal-hypothesis world and the signal world.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from .acoustic_graph import AcousticGraph, EdgeType, GraphNode, NodeType
from .mechanisms import (
    DSPLayer, EnvironmentalReflectionMechanism, Mechanism,
    get_mechanism, list_mechanisms,
)
from .models import Environment, ListenerState, MaterialState, PhysicsMode, Seed


class AcousticCompiler:
    """Compile an AcousticGraph into a renderer-ready recipe.

    The existing renderer expects:
    {
      name, duration,
      layers: [{type, wave, f0, f1, start, dur, a, d, s, r, gain, pan,
                fm_ratio, fm_index, filter}],
      reverb: {mix, decay}
    }

    The compiler:
    1. Walks nodes in topological order
    2. Compiles each mechanism node into DSPLayers
    3. Accumulates propagation delays from edges
    4. Applies listener modeling (Prompt 6)
    5. Computes environment/reverb parameters
    6. Outputs a recipe JSON compatible with the existing renderer
    """

    def __init__(self, max_layers: int = 8):
        self.max_layers = max_layers

    def compile(self, graph: AcousticGraph, seed: Seed = None,
                max_duration: float = 2.0) -> Dict[str, Any]:
        """Compile an acoustic graph into a recipe dict.

        Args:
            graph: The acoustic/event graph to compile.
            seed: Deterministic seed for realization.
            max_duration: Maximum output duration in seconds.

        Returns:
            A recipe dict compatible with the existing Web Audio renderer.
        """
        if seed is None:
            seed = Seed()

        all_layers: List[DSPLayer] = []
        reverb_params = {"mix": 0.1, "decay": 0.5}
        listener_state: Optional[ListenerState] = None
        environment: Optional[Environment] = None

        # Walk in topological order
        ordered_nodes = graph.topological_order()

        # Compute cumulative delays from edges
        node_start_times: Dict[str, float] = {}
        for node in ordered_nodes:
            predecessors = graph.get_predecessors(node.node_id)
            if not predecessors:
                node_start_times[node.node_id] = node.start_time
            else:
                max_pred_time = 0.0
                for pred in predecessors:
                    pred_time = node_start_times.get(pred.node_id, 0.0)
                    # Find edge delay
                    for edge in graph.edges:
                        if edge.source_id == pred.node_id and edge.target_id == node.node_id:
                            pred_time += edge.delay
                            break
                    max_pred_time = max(max_pred_time, pred_time)
                node_start_times[node.node_id] = max_pred_time + node.start_time

        # Compile each node
        for node in ordered_nodes:
            start_offset = node_start_times.get(node.node_id, 0.0)

            if node.node_type == NodeType.LISTENER:
                listener_state = node.listener
                continue

            if node.node_type == NodeType.ENVIRONMENT:
                environment = node.environment
                # Get reverb from environment mechanism
                env_mech = get_mechanism("ENVIRONMENTAL_REFLECTION")
                if env_mech and isinstance(env_mech, EnvironmentalReflectionMechanism):
                    env_params = {}
                    if environment:
                        env_params = {
                            "room_size": environment.room_size,
                            "reflectivity": environment.reflectivity,
                        }
                    reverb_params = env_mech.get_reverb_params(env_params)
                continue

            if node.node_type == NodeType.PROPAGATION:
                # Propagation delays are handled via edge delays
                continue

            # Compile mechanism if present
            if node.mechanism:
                mechanism = get_mechanism(node.mechanism)
                if mechanism:
                    # Gather material from node
                    material = node.material

                    # Build compile params
                    params = dict(node.parameters)
                    params["start"] = start_offset
                    if node.duration is not None:
                        params["duration"] = node.duration

                    # Compile
                    layers = mechanism.compile(
                        params, material,
                        seed=seed.value + hash(node.node_id) & 0xFFFF,
                        physics_mode=graph.physics_mode,
                    )

                    # Apply energy transfer weights from incoming edges
                    weight = 1.0
                    for edge in graph.edges:
                        if edge.target_id == node.node_id:
                            weight *= edge.weight
                    for layer in layers:
                        layer.gain *= weight

                    all_layers.extend(layers)

        # Apply listener modeling (Prompt 6)
        if listener_state:
            all_layers = self._apply_listener(all_layers, listener_state, environment)

        # Cap layers and duration
        all_layers = self._prioritize_layers(all_layers)

        # Build recipe
        duration = 0.0
        for l in all_layers:
            end = l.start + l.dur + l.r + 0.05
            duration = max(duration, end)
        duration = min(duration, max_duration)

        recipe = {
            "name": graph.metadata.get("name", "superlarynx_output"),
            "duration": round(duration, 3),
            "layers": [l.to_dict() for l in all_layers],
            "reverb": {
                "mix": round(min(0.4, reverb_params.get("mix", 0.1)), 3),
                "decay": round(min(2.5, reverb_params.get("decay", 0.5)), 3),
            },
        }

        return recipe

    def _apply_listener(self, layers: List[DSPLayer],
                        listener: ListenerState,
                        environment: Optional[Environment]) -> List[DSPLayer]:
        """Apply listener modeling to all layers (Prompt 6).

        Models: distance attenuation, occlusion, directionality.
        """
        if not listener:
            return layers

        distance = max(0.1, listener.distance)
        occlusion = listener.occlusion

        for layer in layers:
            # Distance attenuation (inverse square, capped)
            atten = min(1.0, 1.0 / (distance * distance)) if distance > 1.0 else 1.0
            layer.gain *= atten

            # Occlusion — low-pass filtering effect
            if occlusion > 0.1 and layer.filter is None:
                cutoff = 8000 * (1 - occlusion * 0.8)
                layer.filter = {
                    "type": "lowpass",
                    "f0": cutoff,
                    "f1": cutoff,
                    "q": 0.7,
                }
            elif occlusion > 0.1 and layer.filter:
                # Reduce existing filter frequency
                if layer.filter.get("type") == "lowpass":
                    factor = 1 - occlusion * 0.5
                    layer.filter["f0"] *= factor
                    layer.filter["f1"] *= factor

            # Frequency-dependent air absorption for distance
            if distance > 3.0 and environment and environment.frequency_dependent_attenuation:
                if layer.filter is None:
                    cutoff = 16000 / (1 + (distance - 3) * 0.1)
                    layer.filter = {
                        "type": "lowpass",
                        "f0": cutoff,
                        "f1": cutoff,
                        "q": 0.5,
                    }

        return layers

    def _prioritize_layers(self, layers: List[DSPLayer]) -> List[DSPLayer]:
        """Reduce to max_layers by keeping the most perceptually important.

        Priority: higher gain and earlier start time = more important.
        """
        if len(layers) <= self.max_layers:
            return layers

        # Score each layer
        scored = []
        for i, l in enumerate(layers):
            importance = l.gain * 0.6 + (1.0 / (1.0 + l.start)) * 0.4
            scored.append((importance, i, l))
        scored.sort(reverse=True)

        return [l for _, _, l in scored[:self.max_layers]]


# ---------------------------------------------------------------------------
# High-level compilation function
# ---------------------------------------------------------------------------

def compile_graph_to_recipe(graph: AcousticGraph,
                            seed: Optional[Seed] = None,
                            max_duration: float = 2.0,
                            max_layers: int = 8) -> Dict[str, Any]:
    """Convenience function: compile an acoustic graph into a recipe.

    Args:
        graph: The acoustic/event graph.
        seed: Realization seed.
        max_duration: Cap on output duration.
        max_layers: Maximum DSP layers in the recipe.

    Returns:
        Recipe dict compatible with the existing Web Audio renderer.
    """
    compiler = AcousticCompiler(max_layers=max_layers)
    return compiler.compile(graph, seed, max_duration)
