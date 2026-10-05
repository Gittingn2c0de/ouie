"""Superlarynx Mechanism Library — Prompt 19.

Higher-level acoustic processes built above the existing DSP primitives
(osc/noise/FM/filter/envelope). Each mechanism compiles into combinations
of those primitives.

This is how Superlarynx escapes the "oscillator recipe" trap.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .models import Distribution, MaterialState, PhysicsMode


# ---------------------------------------------------------------------------
# Layer (the low-level DSP primitive — matches existing recipe schema)
# ---------------------------------------------------------------------------

@dataclass
class DSPLayer:
    """A single DSP layer matching the existing renderer's recipe format.

    This is the atomic unit that the Web Audio renderer understands.
    """
    type: str = "osc"                # osc | fm | noise
    wave: str = "sine"               # sine | triangle | square | sawtooth
    f0: float = 440.0                # start frequency Hz
    f1: float = 440.0                # end frequency Hz
    start: float = 0.0               # start time (s)
    dur: float = 0.2                 # duration (s)
    a: float = 0.005                 # attack (s)
    d: float = 0.1                   # decay (s)
    s: float = 0.0                   # sustain (0-1)
    r: float = 0.1                   # release (s)
    gain: float = 0.5                # 0-1
    pan: float = 0.0                 # -1..1
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


# ---------------------------------------------------------------------------
# Mechanism base class
# ---------------------------------------------------------------------------

class Mechanism:
    """Base class for high-level acoustic mechanisms.

    Each subclass compiles material properties + parameters into
    one or more DSPLayers.
    """
    name: str = "GENERIC"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        """Compile this mechanism into DSP layers."""
        raise NotImplementedError

    @staticmethod
    def _resolve_material(material: Optional[MaterialState],
                          seed: int = 0) -> Dict[str, float]:
        """Resolve material distributions to concrete values."""
        if material is None:
            return {}
        return material.resolve(seed)


# ---------------------------------------------------------------------------
# Specific mechanisms (Prompt 19)
# ---------------------------------------------------------------------------

class ImpulseMechanism(Mechanism):
    """IMPULSE — Short broadband energy injection.

    Compiles to: short noise burst + bandpass + fast envelope.
    """
    name = "IMPULSE"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        hardness = mat.get("hardness", 0.5)
        mass = mat.get("mass", 0.1)

        # Harder materials → brighter, shorter impulse
        brightness = 2000 + hardness * 12000
        attack = 0.001 + (1 - hardness) * 0.004
        decay = 0.005 + (1 - hardness) * 0.02
        gain = min(0.8, 0.3 + mass * 0.5)

        return [DSPLayer(
            type="noise", start=params.get("start", 0.0),
            dur=decay * 2, a=attack, d=decay, s=0.0, r=decay,
            gain=gain * rng.uniform(0.9, 1.0),
            pan=params.get("pan", 0.0),
            filter={"type": "bandpass", "f0": brightness, "f1": brightness * 0.6,
                    "q": 1.5 + hardness * 3},
        )]


class CollisionMechanism(Mechanism):
    """COLLISION — Impact with modal response.

    Compiles to: impulse + modal resonances + body response.
    """
    name = "COLLISION"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        layers = []
        start = params.get("start", 0.0)
        hardness = mat.get("hardness", 0.5)
        damping = mat.get("damping", 0.3)
        elasticity = mat.get("elasticity", 0.5)
        mass = mat.get("mass", 0.5)

        # Impact impulse
        imp = ImpulseMechanism()
        layers.extend(imp.compile(params, material, seed, physics_mode))

        # Modal resonances — number depends on material complexity
        n_modes = max(1, min(4, int(3 * (1 - damping) + 1)))
        base_freq = 100 + (1 - mass) * 800 + elasticity * 400

        for i in range(n_modes):
            mode_ratio = [1.0, 2.37, 4.12, 6.58][i] if i < 4 else (i + 1) * 1.5
            # Add slight inharmonicity for realism
            inharm = 1.0 + rng.gauss(0, 0.02) if physics_mode != PhysicsMode.IMAGINARY else 1.0 + rng.gauss(0, 0.1)
            freq = base_freq * mode_ratio * inharm
            if freq > 16000:
                continue

            mode_decay = (0.05 + damping * 0.3) / (1 + i * 0.3)
            mode_gain = (0.4 / (1 + i * 0.5)) * (1 - damping * 0.5)

            layers.append(DSPLayer(
                type="osc", wave="sine",
                f0=freq, f1=freq * (0.98 + damping * 0.02),
                start=start + 0.001 * i,
                dur=mode_decay * 3,
                a=0.001, d=mode_decay, s=0.1 * (1 - damping), r=mode_decay * 2,
                gain=mode_gain * rng.uniform(0.85, 1.0),
                pan=rng.uniform(-0.15, 0.15),
            ))

        return layers


class ContactMechanism(Mechanism):
    """CONTACT — Sustained contact interaction (not impact).

    Compiles to: filtered noise + resonance excitation.
    """
    name = "CONTACT"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        roughness = mat.get("roughness", 0.5)
        hardness = mat.get("hardness", 0.5)
        start = params.get("start", 0.0)
        dur = params.get("duration", 0.3)

        layers = []
        # Surface noise
        noise_freq = 1000 + roughness * 8000
        layers.append(DSPLayer(
            type="noise", start=start, dur=dur,
            a=0.01, d=dur * 0.3, s=0.4 + roughness * 0.3, r=0.05,
            gain=0.15 + roughness * 0.25,
            filter={"type": "bandpass", "f0": noise_freq, "f1": noise_freq * 0.8,
                    "q": 2 + roughness * 5},
        ))

        # Body resonance from contact
        if hardness > 0.3:
            body_freq = 200 + hardness * 600
            layers.append(DSPLayer(
                type="osc", wave="sine",
                f0=body_freq, f1=body_freq,
                start=start, dur=dur,
                a=0.02, d=dur * 0.5, s=0.2, r=0.1,
                gain=0.1 + hardness * 0.15,
            ))

        return layers


class FrictionMechanism(Mechanism):
    """FRICTION — Sliding/rubbing interaction.

    Compiles to: modulated noise + surface texture filtering.
    """
    name = "FRICTION"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        roughness = mat.get("roughness", 0.5)
        hardness = mat.get("hardness", 0.5)
        start = params.get("start", 0.0)
        dur = params.get("duration", 0.5)
        velocity = params.get("velocity", 0.5)

        layers = []
        center_freq = 800 + roughness * 6000 + velocity * 2000

        # Main friction noise
        layers.append(DSPLayer(
            type="noise", start=start, dur=dur,
            a=0.02, d=dur * 0.2, s=0.5 + velocity * 0.3, r=0.05,
            gain=0.2 + roughness * 0.3 + velocity * 0.15,
            filter={"type": "bandpass", "f0": center_freq,
                    "f1": center_freq * (0.7 + velocity * 0.3),
                    "q": 1 + roughness * 4},
        ))

        # High-frequency scrape component
        if roughness > 0.4:
            layers.append(DSPLayer(
                type="noise", start=start, dur=dur * 0.8,
                a=0.01, d=dur * 0.3, s=0.3, r=0.03,
                gain=roughness * 0.15,
                filter={"type": "highpass", "f0": 4000 + roughness * 6000,
                        "f1": 3000 + roughness * 5000, "q": 2},
            ))

        return layers


class ModalResponseMechanism(Mechanism):
    """MODAL_RESPONSE — Resonant modal excitation of a body.

    Parallel bandpass-filtered oscillators at modal frequencies.
    Material determines frequency ratios, damping, and density.
    """
    name = "MODAL_RESPONSE"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        damping = mat.get("damping", 0.3)
        elasticity = mat.get("elasticity", 0.5)
        mass = mat.get("mass", 0.5)
        start = params.get("start", 0.0)

        layers = []
        base_freq = params.get("base_freq", 150 + (1 - mass) * 600 + elasticity * 300)
        n_modes = params.get("n_modes", max(1, min(5, int(4 * (1 - damping)))))

        # Modal ratios vary by geometry
        geometry = params.get("geometry", "generic")
        if geometry == "plate":
            ratios = [1.0, 1.59, 2.14, 2.65, 3.16]
        elif geometry == "cylinder":
            ratios = [1.0, 2.76, 5.40, 8.93, 13.34]
        elif geometry == "sphere":
            ratios = [1.0, 1.41, 1.73, 2.0, 2.24]
        else:
            ratios = [1.0, 2.2, 3.8, 5.9, 8.5]

        for i in range(min(n_modes, len(ratios))):
            freq = base_freq * ratios[i] * rng.uniform(0.97, 1.03)
            if freq > 16000:
                continue

            decay_time = (0.03 + (1 - damping) * 0.5) / (1 + i * 0.4)
            mode_gain = (0.35 / (1 + i * 0.6)) * (1 - damping * 0.4)

            layers.append(DSPLayer(
                type="osc", wave="sine",
                f0=freq, f1=freq * (0.995 + damping * 0.005),
                start=start + i * 0.0005,
                dur=decay_time * 2,
                a=0.001, d=decay_time, s=0.05 * (1 - damping), r=decay_time * 1.5,
                gain=mode_gain * rng.uniform(0.85, 1.0),
                pan=rng.uniform(-0.2, 0.2),
            ))

        return layers


class ScrapeMechanism(Mechanism):
    """SCRAPE — Time-varying contact with surface texture.

    Compiles to: time-varying filtered noise with modulation.
    """
    name = "SCRAPE"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        roughness = mat.get("roughness", 0.6)
        start = params.get("start", 0.0)
        dur = params.get("duration", 0.4)

        layers = []
        # Main scrape body — frequency sweeps
        f_start = 1000 + roughness * 5000
        f_end = f_start * rng.uniform(0.5, 1.5)

        layers.append(DSPLayer(
            type="noise", start=start, dur=dur,
            a=0.005, d=dur * 0.3, s=0.5, r=dur * 0.2,
            gain=0.25 + roughness * 0.2,
            filter={"type": "bandpass", "f0": f_start, "f1": f_end,
                    "q": 2 + roughness * 6},
        ))

        # Granular micro-events for texture
        n_grains = int(5 + roughness * 15)
        for i in range(min(n_grains, 6)):  # cap at 6 layers
            t = start + rng.uniform(0, dur * 0.8)
            grain_f = f_start * rng.uniform(0.5, 2.0)
            layers.append(DSPLayer(
                type="noise", start=t, dur=rng.uniform(0.005, 0.02),
                a=0.001, d=0.005, s=0.0, r=0.005,
                gain=rng.uniform(0.05, 0.15) * roughness,
                filter={"type": "bandpass", "f0": grain_f, "f1": grain_f,
                        "q": rng.uniform(2, 8)},
            ))

        return layers


class ResonanceMechanism(Mechanism):
    """RESONANCE — Sustained resonant ringing.

    For cavities, tubes, rooms, bodies.
    """
    name = "RESONANCE"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        damping = mat.get("damping", 0.2)
        start = params.get("start", 0.0)
        freq = params.get("frequency", 200)
        dur = params.get("duration", 0.5)

        layers = []
        # Fundamental
        decay_time = dur * (1 - damping * 0.7)
        layers.append(DSPLayer(
            type="osc", wave="sine",
            f0=freq, f1=freq,
            start=start, dur=decay_time,
            a=0.005, d=decay_time * 0.4, s=0.3 * (1 - damping), r=decay_time * 0.5,
            gain=0.4,
        ))

        # Harmonics
        for h in range(2, 4):
            h_freq = freq * h * rng.uniform(0.99, 1.01)
            if h_freq > 12000:
                break
            layers.append(DSPLayer(
                type="osc", wave="sine",
                f0=h_freq, f1=h_freq,
                start=start + 0.001, dur=decay_time * (0.7 ** h),
                a=0.005, d=decay_time * 0.3 * (0.7 ** h), s=0.1, r=decay_time * 0.3,
                gain=0.2 / h,
            ))

        return layers


class AirflowMechanism(Mechanism):
    """AIRFLOW — Wind, breath, pneumatic sounds.

    Compiles to: shaped noise with spectral envelope.
    """
    name = "AIRFLOW"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        start = params.get("start", 0.0)
        dur = params.get("duration", 0.5)
        intensity = params.get("intensity", 0.5)

        layers = []
        # Low turbulence
        layers.append(DSPLayer(
            type="noise", start=start, dur=dur,
            a=dur * 0.2, d=dur * 0.3, s=0.4 + intensity * 0.3, r=dur * 0.3,
            gain=0.15 + intensity * 0.2,
            filter={"type": "lowpass", "f0": 800 + intensity * 3000,
                    "f1": 600 + intensity * 2000, "q": 0.7},
        ))

        # High-frequency air hiss
        layers.append(DSPLayer(
            type="noise", start=start, dur=dur * 0.8,
            a=dur * 0.15, d=dur * 0.3, s=0.3, r=dur * 0.2,
            gain=0.08 + intensity * 0.12,
            filter={"type": "highpass", "f0": 3000 + intensity * 5000,
                    "f1": 2500 + intensity * 4000, "q": 1.0},
        ))

        return layers


class EnvironmentalReflectionMechanism(Mechanism):
    """ENVIRONMENTAL_REFLECTION — Room response applied to existing signal.

    This mechanism affects the reverb parameters of the recipe rather than
    adding new layers.
    """
    name = "ENVIRONMENTAL_REFLECTION"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        # This mechanism modifies recipe-level reverb rather than adding layers
        # Return empty — the compiler handles this at the recipe level
        return []

    def get_reverb_params(self, params: Dict[str, Any]) -> Dict[str, float]:
        """Compute reverb parameters from environment."""
        room_size = params.get("room_size", "medium")
        reflectivity = params.get("reflectivity", 0.5)

        size_map = {"small": 0.3, "medium": 0.6, "large": 1.2, "outdoor": 0.1}
        decay = size_map.get(room_size, 0.6) * (0.5 + reflectivity)
        mix = min(0.4, 0.05 + reflectivity * 0.3)

        return {"mix": mix, "decay": min(2.5, decay)}


class MembraneMechanism(Mechanism):
    """MEMBRANE — Drum-like membrane response."""
    name = "MEMBRANE"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        start = params.get("start", 0.0)
        tension = mat.get("stiffness", 0.5)
        damping = mat.get("damping", 0.3)

        base_freq = 60 + tension * 200
        layers = []

        # Membrane modes (circular membrane ratios)
        ratios = [1.0, 1.593, 2.136, 2.296, 2.653]
        for i, r in enumerate(ratios[:3]):
            freq = base_freq * r * rng.uniform(0.98, 1.02)
            decay = (0.1 + (1 - damping) * 0.4) / (1 + i * 0.5)
            layers.append(DSPLayer(
                type="osc", wave="sine",
                f0=freq, f1=freq * 0.95,
                start=start, dur=decay * 2,
                a=0.001, d=decay, s=0.05, r=decay,
                gain=0.4 / (1 + i * 0.7),
            ))

        # Attack noise
        layers.append(DSPLayer(
            type="noise", start=start, dur=0.01,
            a=0.001, d=0.005, s=0.0, r=0.005,
            gain=0.3,
            filter={"type": "lowpass", "f0": 3000, "f1": 1000, "q": 1.0},
        ))

        return layers


class StringMechanism(Mechanism):
    """STRING — Vibrating string with harmonics and inharmonicity."""
    name = "STRING"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        start = params.get("start", 0.0)
        freq = params.get("frequency", 220)
        damping = mat.get("damping", 0.2)
        stiffness = mat.get("stiffness", 0.3)

        layers = []
        n_harmonics = max(2, min(5, int(5 * (1 - damping))))

        for h in range(1, n_harmonics + 1):
            # Stiffness causes inharmonicity (Prompt 19)
            inharm = 1.0 + stiffness * 0.001 * h * h
            h_freq = freq * h * inharm * rng.uniform(0.999, 1.001)
            if h_freq > 14000:
                break

            decay = (0.1 + (1 - damping) * 0.8) / (h ** 0.5)
            layers.append(DSPLayer(
                type="osc", wave="sine" if h <= 3 else "triangle",
                f0=h_freq, f1=h_freq,
                start=start, dur=decay * 1.5,
                a=0.002, d=decay, s=0.1 * (1 - damping), r=decay * 0.8,
                gain=0.35 / (h ** 0.7) * rng.uniform(0.9, 1.0),
                pan=rng.uniform(-0.1, 0.1),
            ))

        return layers


class FluidMechanism(Mechanism):
    """FLUID — Liquid, splash, bubble, drip sounds."""
    name = "FLUID"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        start = params.get("start", 0.0)
        dur = params.get("duration", 0.3)
        size = params.get("size", 0.5)  # 0=small drip, 1=large splash

        layers = []

        # Bubble oscillation — frequency glides down as bubble rises
        bubble_f = 500 + (1 - size) * 2000
        layers.append(DSPLayer(
            type="osc", wave="sine",
            f0=bubble_f, f1=bubble_f * 0.6,
            start=start, dur=dur * 0.5,
            a=0.002, d=dur * 0.15, s=0.2, r=dur * 0.2,
            gain=0.25 + size * 0.15,
        ))

        # Splash noise
        layers.append(DSPLayer(
            type="noise", start=start, dur=dur,
            a=0.003, d=dur * 0.2, s=0.2 + size * 0.3, r=dur * 0.4,
            gain=0.15 + size * 0.2,
            filter={"type": "bandpass", "f0": 1000 + size * 3000,
                    "f1": 800 + size * 2000, "q": 1.5},
        ))

        return layers


class RattleMechanism(Mechanism):
    """RATTLE — Multiple small, rapid impacts."""
    name = "RATTLE"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        start = params.get("start", 0.0)
        dur = params.get("duration", 0.3)
        density_param = params.get("density", 0.5)

        layers = []
        n_events = int(3 + density_param * 12)
        imp = ImpulseMechanism()

        for i in range(min(n_events, 6)):  # cap layers
            t = start + rng.uniform(0, dur * 0.9)
            sub_params = {
                "start": t,
                "pan": rng.uniform(-0.3, 0.3),
            }
            sub_layers = imp.compile(sub_params, material, seed + i, physics_mode)
            for sl in sub_layers:
                sl.gain *= rng.uniform(0.3, 1.0) * 0.5  # varied intensity
            layers.extend(sub_layers)

        return layers


class NonlinearContactMechanism(Mechanism):
    """NONLINEAR_CONTACT — Buzzing, chattering, nonlinear vibration.

    Uses FM synthesis to represent nonlinear interactions.
    """
    name = "NONLINEAR_CONTACT"

    def compile(self, params: Dict[str, Any], material: Optional[MaterialState] = None,
                seed: int = 0, physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
                ) -> List[DSPLayer]:
        rng = random.Random(seed)
        mat = self._resolve_material(material, seed)
        start = params.get("start", 0.0)
        dur = params.get("duration", 0.3)
        intensity = params.get("intensity", 0.5)
        base_freq = params.get("frequency", 150)

        layers = []
        layers.append(DSPLayer(
            type="fm", wave="sine",
            f0=base_freq, f1=base_freq * 0.9,
            start=start, dur=dur,
            a=0.005, d=dur * 0.3, s=0.3, r=dur * 0.3,
            gain=0.3 + intensity * 0.2,
            fm_ratio=rng.uniform(1.5, 5.0),
            fm_index=intensity * 8,
        ))

        return layers


# ---------------------------------------------------------------------------
# Mechanism Registry
# ---------------------------------------------------------------------------

MECHANISM_REGISTRY: Dict[str, Mechanism] = {
    "IMPULSE": ImpulseMechanism(),
    "COLLISION": CollisionMechanism(),
    "CONTACT": ContactMechanism(),
    "FRICTION": FrictionMechanism(),
    "MODAL_RESPONSE": ModalResponseMechanism(),
    "SCRAPE": ScrapeMechanism(),
    "RESONANCE": ResonanceMechanism(),
    "AIRFLOW": AirflowMechanism(),
    "ENVIRONMENTAL_REFLECTION": EnvironmentalReflectionMechanism(),
    "MEMBRANE": MembraneMechanism(),
    "STRING": StringMechanism(),
    "FLUID": FluidMechanism(),
    "RATTLE": RattleMechanism(),
    "NONLINEAR_CONTACT": NonlinearContactMechanism(),
}


def get_mechanism(name: str) -> Optional[Mechanism]:
    """Look up a mechanism by name."""
    return MECHANISM_REGISTRY.get(name.upper())


def list_mechanisms() -> List[str]:
    """Return all available mechanism names."""
    return list(MECHANISM_REGISTRY.keys())
