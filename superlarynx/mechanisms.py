"""Superlarynx Mechanism Library — Physics-Based Rebuild.

Implements real mechanism compilers (not presets) for:
- AIRFLOW
- COLLISION
- MODAL_RESPONSE
- FLUID_IMPACT
- NONLINEAR_CONTACT
- STRUCTURAL_COUPLING
- ENVIRONMENTAL_PROPAGATION

Mechanisms now use the causal context (inputs, energy, relational properties)
to generate signal behavior.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .models import Distribution, MaterialState, PhysicsMode
from .acoustic_graph import AcousticGraph, GraphNode, NodeType

@dataclass
class DSPLayer:
    type: str = "osc"
    wave: str = "sine"
    f0: float = 440.0
    f1: float = 440.0
    start: float = 0.0
    dur: float = 0.2
    a: float = 0.005
    d: float = 0.1
    s: float = 0.0
    r: float = 0.1
    gain: float = 0.5
    pan: float = 0.0
    fm_ratio: float = 2.0
    fm_index: float = 2.0
    filter: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "type": self.type, "wave": self.wave,
            "f0": self.f0, "f1": self.f1,
            "start": self.start, "dur": self.dur,
            "a": self.a, "d": self.d, "s": self.s, "r": self.r,
            "gain": self.gain, "pan": self.pan,
        }
        if self.type == "fm":
            d["fm_ratio"] = self.fm_ratio
            d["fm_index"] = self.fm_index
        if self.filter:
            d["filter"] = self.filter
        return d

class MechanismContext:
    def __init__(self, node: GraphNode, graph: AcousticGraph, start_time: float, state: Dict[str, Any]):
        self.node = node
        self.graph = graph
        self.start_time = start_time
        self.state = state  # Physical state (energy, velocity, mass, etc.) computed in compiler

class Mechanism:
    name: str = "GENERIC"
    implementation_status: str = "IMPLEMENTED"  # IMPLEMENTED, APPROXIMATED, UNIMPLEMENTED

    def compile(self, ctx: MechanismContext, seed: int = 0) -> List[DSPLayer]:
        raise NotImplementedError

    @staticmethod
    def _resolve_material(material: Optional[MaterialState], seed: int = 0) -> Dict[str, float]:
        if material is None: return {}
        return material.resolve(seed)


class ImpulseMechanism(Mechanism):
    name = "IMPULSE"
    
    def compile(self, ctx: MechanismContext, seed: int = 0) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(ctx.node.material, seed)
        hardness = mat.get("hardness", 0.5)
        energy = ctx.state.get("energy", 1.0)
        
        brightness = 2000 + hardness * 12000
        attack = 0.001 + (1 - hardness) * 0.004
        decay = 0.005 + (1 - hardness) * 0.02
        gain = min(0.8, 0.2 + energy * 0.5)

        return [DSPLayer(
            type="noise", start=ctx.start_time, dur=decay * 2,
            a=attack, d=decay, s=0.0, r=decay, gain=gain,
            filter={"type": "bandpass", "f0": brightness, "f1": brightness * 0.6, "q": 1.5 + hardness * 3},
        )]


class CollisionMechanism(Mechanism):
    """COLLISION — Relational impact between object A and object B."""
    name = "COLLISION"

    def compile(self, ctx: MechanismContext, seed: int = 0) -> List[DSPLayer]:
        rng = random.Random(seed)
        
        # Find incoming objects to make collision relational
        preds = ctx.graph.get_predecessors(ctx.node.node_id)
        objects = [p for p in preds if p.node_type == NodeType.OBJECT]
        
        mat_A = self._resolve_material(objects[0].material if len(objects) > 0 else ctx.node.material, seed)
        mat_B = self._resolve_material(objects[1].material if len(objects) > 1 else ctx.node.material, seed + 1)
        
        # Effective properties based on interacting materials
        hardness = min(mat_A.get("hardness", 0.5), mat_B.get("hardness", 0.5))
        damping = max(mat_A.get("damping", 0.3), mat_B.get("damping", 0.3))
        energy = ctx.state.get("energy", 1.0)
        velocity = ctx.state.get("velocity", 1.0)
        
        layers = []
        
        # 1. Impact Transient (dependent on relative velocity and mutual hardness)
        transient_dur = 0.001 + (1 - hardness) * 0.01 / max(0.1, velocity)
        brightness = 1000 + hardness * 10000 * min(1.0, velocity)
        layers.append(DSPLayer(
            type="noise", start=ctx.start_time, dur=transient_dur * 2,
            a=0.001, d=transient_dur, s=0, r=transient_dur, gain=min(0.9, energy * 0.6),
            filter={"type": "bandpass", "f0": brightness, "f1": brightness*0.5, "q": 1.0 + hardness * 2}
        ))
        
        # 2. Transferred Modal Excitation to both objects
        for obj_idx, mat in enumerate([mat_A, mat_B]):
            mass = mat.get("mass", 0.5)
            elasticity = mat.get("elasticity", 0.5)
            obj_damping = mat.get("damping", 0.3)
            
            base_freq = 100 + (1 - mass) * 800 + elasticity * 400
            n_modes = max(1, min(4, int(3 * (1 - obj_damping) + 1)))
            
            for i in range(n_modes):
                mode_ratio = [1.0, 2.37, 4.12, 6.58][i] if i < 4 else (i + 1) * 1.5
                inharm = 1.0 + rng.gauss(0, 0.02)
                freq = base_freq * mode_ratio * inharm
                if freq > 16000: continue

                mode_decay = (0.05 + obj_damping * 0.3) / (1 + i * 0.3)
                mode_gain = (0.4 / (1 + i * 0.5)) * (1 - obj_damping * 0.5) * energy

                layers.append(DSPLayer(
                    type="osc", wave="sine", f0=freq, f1=freq * (0.98 + obj_damping * 0.02),
                    start=ctx.start_time + 0.001 * i, dur=mode_decay * 3,
                    a=0.001, d=mode_decay, s=0.1 * (1 - obj_damping), r=mode_decay * 2,
                    gain=mode_gain * rng.uniform(0.85, 1.0),
                    pan=rng.uniform(-0.15, 0.15) if obj_idx == 0 else rng.uniform(-0.15, 0.15) * -1
                ))
        return layers


class ModalResponseMechanism(Mechanism):
    """MODAL_RESPONSE — Real modal resonator excited by incoming energy."""
    name = "MODAL_RESPONSE"

    def compile(self, ctx: MechanismContext, seed: int = 0) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(ctx.node.material, seed)
        damping = mat.get("damping", 0.3)
        elasticity = mat.get("elasticity", 0.5)
        mass = mat.get("mass", 0.5)
        
        energy = ctx.state.get("incoming_energy", 1.0)
        
        base_freq = ctx.node.parameters.get("base_freq", 150 + (1 - mass) * 600 + elasticity * 300)
        n_modes = ctx.node.parameters.get("n_modes", max(1, min(8, int(6 * (1 - damping)))))
        geometry = ctx.node.parameters.get("geometry", "generic")
        
        if geometry == "plate": ratios = [1.0, 1.59, 2.14, 2.65, 3.16, 3.82, 4.5]
        elif geometry == "cylinder": ratios = [1.0, 2.76, 5.40, 8.93, 13.34, 18.6]
        elif geometry == "sphere": ratios = [1.0, 1.41, 1.73, 2.0, 2.24, 2.45]
        else: ratios = [1.0, 2.2, 3.8, 5.9, 8.5, 11.4]

        layers = []
        for i in range(min(n_modes, len(ratios))):
            freq = base_freq * ratios[i] * rng.uniform(0.97, 1.03)
            if freq > 16000: continue

            # Modal bandwidth and decay
            decay_time = (0.03 + (1 - damping) * 0.8) / (1 + i * 0.5)
            # Excitation sensitivity (higher modes need sharper transients to excite)
            mode_gain = (0.4 / (1 + i * 0.6)) * (1 - damping * 0.4) * energy

            layers.append(DSPLayer(
                type="osc", wave="sine", f0=freq, f1=freq * (0.995 + damping * 0.005),
                start=ctx.start_time + i * 0.0005, dur=decay_time * 2,
                a=0.001, d=decay_time, s=0.05 * (1 - damping), r=decay_time * 1.5,
                gain=mode_gain * rng.uniform(0.85, 1.0)
            ))
        return layers


class StructuralCouplingMechanism(Mechanism):
    """STRUCTURAL_COUPLING — Transfers energy to excite recipient structure."""
    name = "STRUCTURAL_COUPLING"
    
    def compile(self, ctx: MechanismContext, seed: int = 0) -> List[DSPLayer]:
        # Evaluated purely via causal state propagation in the compiler.
        # It transfers energy from predecessor to successor, generating no direct sound.
        return []


class AirflowMechanism(Mechanism):
    """AIRFLOW — Time-varying pressure/flow process."""
    name = "AIRFLOW"

    def compile(self, ctx: MechanismContext, seed: int = 0) -> List[DSPLayer]:
        rng = random.Random(seed)
        dur = ctx.node.duration or 2.0
        energy = ctx.state.get("energy", 1.0)
        velocity = ctx.state.get("velocity", 0.5) # Mean flow
        
        layers = []
        # Model gusts using overlapping noise bursts with varying filter sweeps
        num_gusts = max(1, int(dur * 2 * velocity))
        
        for i in range(num_gusts):
            gust_start = ctx.start_time + rng.uniform(0, dur * 0.8)
            gust_dur = rng.uniform(0.2, 0.8) / max(0.1, velocity)
            gust_intensity = energy * rng.uniform(0.5, 1.0)
            
            f_center = 200 + velocity * 1000 + gust_intensity * 500
            
            layers.append(DSPLayer(
                type="noise", start=gust_start, dur=gust_dur,
                a=gust_dur * 0.3, d=gust_dur * 0.4, s=0.3, r=gust_dur * 0.3,
                gain=0.15 * gust_intensity,
                filter={"type": "bandpass", "f0": f_center, "f1": f_center * rng.uniform(0.8, 1.2), "q": 1.0}
            ))
            
            # High frequency turbulence
            if velocity > 0.5:
                layers.append(DSPLayer(
                    type="noise", start=gust_start, dur=gust_dur * 0.8,
                    a=gust_dur * 0.2, d=gust_dur * 0.3, s=0.1, r=gust_dur * 0.3,
                    gain=0.08 * gust_intensity * velocity,
                    filter={"type": "highpass", "f0": 3000 + velocity * 2000, "f1": 3500 + velocity * 2000, "q": 0.5}
                ))
        return layers


class FluidImpactMechanism(Mechanism):
    """FLUID_IMPACT — Rain/droplet population with distributed impacts."""
    name = "FLUID_IMPACT"

    def compile(self, ctx: MechanismContext, seed: int = 0) -> List[DSPLayer]:
        rng = random.Random(seed)
        dur = ctx.node.duration or 1.0
        energy = ctx.state.get("energy", 1.0)
        density = ctx.node.parameters.get("density", 0.5)
        
        layers = []
        # Calculate number of droplets based on density and duration
        num_drops = int(10 + density * 50 * dur)
        
        for i in range(min(num_drops, 20)):  # Cap layers to prevent overloading WebAudio
            t = ctx.start_time + rng.uniform(0, dur)
            size = rng.gauss(0.5, 0.2)
            
            f_impact = 1500 + (1 - size) * 4000
            # A single droplet is a very short ping
            layers.append(DSPLayer(
                type="osc", wave="sine", f0=f_impact, f1=f_impact*0.8,
                start=t, dur=0.02, a=0.001, d=0.01, s=0, r=0.01,
                gain=0.05 * energy * size, pan=rng.uniform(-0.5, 0.5)
            ))
            # With a tiny noise splash
            layers.append(DSPLayer(
                type="noise", start=t, dur=0.03, a=0.001, d=0.015, s=0, r=0.015,
                gain=0.03 * energy * size,
                filter={"type": "highpass", "f0": 2000, "f1": 2000, "q": 1.0}
            ))
            
        return layers


class NonlinearContactMechanism(Mechanism):
    """NONLINEAR_CONTACT — Buzzing/chattering nonlinear interaction."""
    name = "NONLINEAR_CONTACT"

    def compile(self, ctx: MechanismContext, seed: int = 0) -> List[DSPLayer]:
        rng = random.Random(seed)
        dur = ctx.node.duration or 0.3
        energy = ctx.state.get("energy", 1.0)
        base_freq = ctx.node.parameters.get("frequency", 150)
        
        layers = [DSPLayer(
            type="fm", wave="sine", f0=base_freq, f1=base_freq * 0.9,
            start=ctx.start_time, dur=dur, a=0.005, d=dur * 0.3, s=0.3, r=dur * 0.3,
            gain=0.3 * energy, fm_ratio=rng.uniform(1.5, 5.0), fm_index=energy * 8,
        )]
        return layers


class EnvironmentalPropagationMechanism(Mechanism):
    name = "ENVIRONMENTAL_PROPAGATION"
    def compile(self, ctx: MechanismContext, seed: int = 0) -> List[DSPLayer]:
        # Modifies recipe-level reverb, compiler handles this.
        return []


MECHANISM_REGISTRY: Dict[str, Mechanism] = {
    "IMPULSE": ImpulseMechanism(),
    "COLLISION": CollisionMechanism(),
    "MODAL_RESPONSE": ModalResponseMechanism(),
    "STRUCTURAL_COUPLING": StructuralCouplingMechanism(),
    "AIRFLOW": AirflowMechanism(),
    "FLUID": FluidImpactMechanism(),
    "FLUID_IMPACT": FluidImpactMechanism(),
    "NONLINEAR_CONTACT": NonlinearContactMechanism(),
    "ENVIRONMENTAL_REFLECTION": EnvironmentalPropagationMechanism(),
    "ENVIRONMENTAL_PROPAGATION": EnvironmentalPropagationMechanism(),
}

def get_mechanism(name: str) -> Optional[Mechanism]:
    return MECHANISM_REGISTRY.get(name.upper())

def list_mechanisms() -> List[str]:
    return list(MECHANISM_REGISTRY.keys())
