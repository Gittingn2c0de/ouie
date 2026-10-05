"""Superlarynx Acoustic Compiler — Physics-Based Rebuild.

Translates an AcousticGraph into a concrete DSP recipe.
Now includes an explicit physical state simulation pass before mechanism
compilation, preserving temporal invariants and logging compiler traces.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional
import sys

from .acoustic_graph import AcousticGraph, EdgeType, GraphNode, NodeType
from .mechanisms import (
    DSPLayer, MechanismContext, Mechanism,
    get_mechanism, list_mechanisms,
)
from .models import Environment, ListenerState, MaterialState, PhysicsMode, Seed


class AcousticCompiler:
    def __init__(self, max_layers: int = 32):
        self.max_layers = max_layers

    def compile(self, graph: AcousticGraph, seed: Seed = None,
                max_duration: float = 2.0) -> Dict[str, Any]:
        if seed is None: seed = Seed()
        
        # Pull requested max duration from graph metadata if present
        requested_duration = graph.metadata.get("max_duration_s", max_duration)

        all_layers: List[DSPLayer] = []
        reverb_params = {"mix": 0.1, "decay": 0.5}
        listener_state: Optional[ListenerState] = None
        environment: Optional[Environment] = None

        ordered_nodes = graph.topological_order()

        # 1. Physical State Simulation Pass
        # We propagate time, energy, and velocity through the graph.
        node_states = {}
        for node in ordered_nodes:
            preds = graph.get_predecessors(node.node_id)
            state = {"energy": 1.0, "velocity": 1.0, "incoming_energy": 0.0}
            
            # Compute start time based on causal delays
            if not preds:
                start_time = node.start_time
            else:
                max_pred_time = 0.0
                total_energy_transfer = 0.0
                for pred in preds:
                    pred_time = node_states[pred.node_id]["start_time"]
                    # Find edge details
                    for edge in graph.edges:
                        if edge.source_id == pred.node_id and edge.target_id == node.node_id:
                            pred_time += edge.delay
                            total_energy_transfer += edge.weight * node_states[pred.node_id]["energy"]
                            break
                    max_pred_time = max(max_pred_time, pred_time)
                
                start_time = max_pred_time + node.start_time
                state["incoming_energy"] = total_energy_transfer
                state["energy"] = max(0.1, total_energy_transfer)
            
            # Allow node to explicitly override state
            if "velocity" in node.parameters:
                state["velocity"] = node.parameters["velocity"]

            state["start_time"] = start_time
            node_states[node.node_id] = state

        # 2. Mechanism Compilation Pass
        trace = []
        for node in ordered_nodes:
            state = node_states[node.node_id]
            start_time = state["start_time"]

            if node.node_type == NodeType.LISTENER:
                listener_state = node.listener
                continue
            if node.node_type == NodeType.ENVIRONMENT:
                environment = node.environment
                continue
            if node.node_type == NodeType.PROPAGATION:
                continue

            if node.mechanism:
                mechanism = get_mechanism(node.mechanism)
                status = "UNIMPLEMENTED"
                layers = []
                
                if mechanism:
                    status = mechanism.implementation_status
                    ctx = MechanismContext(node=node, graph=graph, start_time=start_time, state=state)
                    layers = mechanism.compile(ctx, seed=seed.value + hash(node.node_id) & 0xFFFF)
                    all_layers.extend(layers)
                else:
                    # Generic approximation for missing mechanisms
                    status = "APPROXIMATED"
                    dur = node.duration or 0.2
                    layers = [DSPLayer(type="osc", wave="triangle", f0=400, f1=400, start=start_time, dur=dur, gain=0.1)]
                    all_layers.extend(layers)
                
                # Trace
                trace.append({
                    "node_id": node.node_id,
                    "mechanism": node.mechanism,
                    "status": status,
                    "state_energy": state["energy"],
                    "generated_layers": len(layers)
                })

        # Apply listener modeling
        if listener_state:
            all_layers = self._apply_listener(all_layers, listener_state, environment)

        # Enforce Temporal Invariants
        # If layers exceed requested_duration, clip their release/durations.
        duration = 0.0
        for l in all_layers:
            end = l.start + l.dur + l.r
            duration = max(duration, end)
        
        if duration > requested_duration:
            # We clip layers that extend beyond the budget, allowing a small 0.1s tail
            for l in all_layers:
                max_allowed = requested_duration - l.start
                if max_allowed <= 0:
                    l.gain = 0 # Silent if it starts after the budget
                else:
                    l.dur = min(l.dur, max_allowed * 0.8)
                    l.r = min(l.r, max_allowed * 0.2)
            duration = requested_duration

        all_layers = self._prioritize_layers(all_layers)

        recipe = {
            "name": graph.metadata.get("name", "superlarynx_output"),
            "duration": round(duration, 3),
            "layers": [l.to_dict() for l in all_layers],
            "reverb": {
                "mix": round(min(0.4, reverb_params.get("mix", 0.1)), 3),
                "decay": round(min(2.5, reverb_params.get("decay", 0.5)), 3),
            },
            "compiler_trace": trace
        }
        return recipe

    def _apply_listener(self, layers: List[DSPLayer],
                        listener: ListenerState,
                        environment: Optional[Environment]) -> List[DSPLayer]:
        if not listener: return layers
        distance = max(0.1, listener.distance)
        occlusion = listener.occlusion
        for layer in layers:
            atten = min(1.0, 1.0 / (distance * distance)) if distance > 1.0 else 1.0
            layer.gain *= atten
            if occlusion > 0.1 and layer.filter is None:
                cutoff = 8000 * (1 - occlusion * 0.8)
                layer.filter = {"type": "lowpass", "f0": cutoff, "f1": cutoff, "q": 0.7}
        return layers

    def _prioritize_layers(self, layers: List[DSPLayer]) -> List[DSPLayer]:
        if len(layers) <= self.max_layers: return layers
        scored = []
        for i, l in enumerate(layers):
            importance = l.gain * 0.6 + (1.0 / (1.0 + l.start)) * 0.4
            scored.append((importance, i, l))
        scored.sort(reverse=True)
        return [l for _, _, l in scored[:self.max_layers]]


def compile_graph_to_recipe(graph: AcousticGraph, seed: Optional[Seed] = None, max_duration: float = 2.0, max_layers: int = 32) -> Dict[str, Any]:
    compiler = AcousticCompiler(max_layers=max_layers)
    return compiler.compile(graph, seed, max_duration)
