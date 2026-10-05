"""Superlarynx Core Data Models — Prompts 2, 4, 5, 7.

Defines the conceptual layers that replace the flat "recipe" representation:
  AcousticSignal, AcousticEvent, Stimulus, ObjectState, MaterialState,
  Environment, EventHistory, Experience, Realization, PhysicsMode,
  PerceptualSpec, CausalHypothesis, Distribution, and Seed.

The persistent learning unit is EXPERIENCE, not a sound file or recipe.
A generated sound is reproducible from its causal state + seed, but not
necessarily identical under a different seed or environmental state.
"""
from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Prompt 5 — Physics Modes
# ---------------------------------------------------------------------------

class PhysicsMode(Enum):
    """How aggressively the compiler constrains mechanisms.

    REAL:      Stay within known physical behavior.
    PLAUSIBLE: Allow abstraction, reduced-order models, perceptual approximations.
    IMAGINARY: Permit physically impossible causes, preserve internally coherent
               acoustic behavior.
    """
    REAL = "real"
    PLAUSIBLE = "plausible"
    IMAGINARY = "imaginary"


# ---------------------------------------------------------------------------
# Prompt 7 — Structural variability via distributions
# ---------------------------------------------------------------------------

@dataclass
class Distribution:
    """A parameter that is not a single value but a probability region.

    Unknown properties become distributions rather than arbitrary singles.
    This enables identity-without-repetition: two nominally identical marbles
    share causal identity but differ through micro-parameter variation.
    """
    mean: float
    std: float = 0.0
    low: Optional[float] = None
    high: Optional[float] = None
    distribution_type: str = "normal"  # normal | uniform | log_normal

    def sample(self, rng=None) -> float:
        """Draw a concrete value from this distribution."""
        import random
        r = rng or random
        if self.distribution_type == "uniform":
            lo = self.low if self.low is not None else self.mean - self.std * 3
            hi = self.high if self.high is not None else self.mean + self.std * 3
            return r.uniform(lo, hi)
        val = r.gauss(self.mean, self.std) if self.std > 0 else self.mean
        if self.low is not None:
            val = max(self.low, val)
        if self.high is not None:
            val = min(self.high, val)
        return val


# ---------------------------------------------------------------------------
# Prompt 2, Layer 4 — Object / Material State
# ---------------------------------------------------------------------------

@dataclass
class MaterialState:
    """Persistent material properties participating in a process.

    Represented as parameter distributions and state variables (Prompt 3).
    Distributions/ranges used where appropriate — essential for identity
    without repetition.
    """
    name: str = ""
    density: Optional[Union[float, Distribution]] = None        # kg/m³
    elasticity: Optional[Union[float, Distribution]] = None     # Young's modulus proxy
    hardness: Optional[Union[float, Distribution]] = None       # 0-1 relative
    stiffness: Optional[Union[float, Distribution]] = None      # 0-1 relative
    damping: Optional[Union[float, Distribution]] = None        # 0-1 (low=resonant)
    roughness: Optional[Union[float, Distribution]] = None      # 0-1 surface roughness
    porosity: Optional[Union[float, Distribution]] = None       # 0-1
    mass: Optional[Union[float, Distribution]] = None           # kg
    temperature: Optional[Union[float, Distribution]] = None    # °C
    moisture: Optional[Union[float, Distribution]] = None       # 0-1
    fracture_state: Optional[Union[float, Distribution]] = None # 0-1 (0=intact)
    geometry: str = ""                 # sphere, cylinder, plate, irregular, etc.
    surface_structure: str = ""        # smooth, rough, pitted, ridged, etc.
    contact_properties: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def resolve(self, seed: int = 0) -> Dict[str, float]:
        """Collapse distributions to concrete values for a given seed."""
        import random
        rng = random.Random(seed)
        out = {}
        for f in [
            "density", "elasticity", "hardness", "stiffness", "damping",
            "roughness", "porosity", "mass", "temperature", "moisture",
            "fracture_state",
        ]:
            v = getattr(self, f)
            if v is None:
                continue
            out[f] = v.sample(rng) if isinstance(v, Distribution) else float(v)
        return out


@dataclass
class ObjectState:
    """A persistent object participating in acoustic events."""
    object_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    material: MaterialState = field(default_factory=MaterialState)
    geometry: str = ""              # shape descriptor
    mass: Optional[Union[float, Distribution]] = None
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    state: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Prompt 2, Layer 5 — Environment
# ---------------------------------------------------------------------------

@dataclass
class ListenerState:
    """Listener modeling (Prompt 6).

    The listener is part of the sound-generation system.
    """
    position: Tuple[float, float, float] = (0.0, 0.0, 2.0)
    distance: float = 2.0
    orientation: Tuple[float, float, float] = (0.0, 0.0, -1.0)
    occlusion: float = 0.0          # 0=clear, 1=fully occluded
    directionality: float = 0.0     # 0=omnidirectional, 1=highly directional


@dataclass
class Environment:
    """Propagation space, boundaries, surfaces, medium, reflections, etc.

    Reduced-order propagation models are the default (Prompt 6).
    """
    name: str = ""
    medium: str = "air"                           # air | water | other
    room_size: str = "medium"                     # small | medium | large | outdoor
    room_dimensions: Tuple[float, float, float] = (5.0, 4.0, 3.0)  # meters
    surface_material: str = ""                    # concrete, wood, tile, etc.
    reflectivity: float = 0.5                     # 0-1
    temperature: float = 20.0                     # °C
    humidity: float = 0.5                         # 0-1
    early_reflections: bool = True
    late_reverberation: bool = True
    frequency_dependent_attenuation: bool = True
    listener: ListenerState = field(default_factory=ListenerState)
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Prompt 2, Layer 3 — Stimulus / Process
# ---------------------------------------------------------------------------

@dataclass
class Stimulus:
    """What physically or perceptually caused an acoustic event.

    Examples: gravity, hand strike, wind, friction, pressure release, etc.
    """
    stimulus_type: str = ""       # gravity, impact, friction, pressure, etc.
    energy: Optional[Union[float, Distribution]] = None
    velocity: Optional[Union[float, Distribution]] = None
    angle: Optional[Union[float, Distribution]] = None
    duration: Optional[Union[float, Distribution]] = None
    source_object: Optional[ObjectState] = None
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Prompt 2, Layer 2 — Acoustic Event
# ---------------------------------------------------------------------------

@dataclass
class AcousticEvent:
    """A temporally bounded perceptual occurrence.

    Examples: impact, scrape, burst, resonance, flutter, crack, rub,
    splash, vibration, etc.
    """
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    event_type: str = ""           # impact, scrape, burst, resonance, flutter, etc.
    start_time: float = 0.0        # seconds
    duration: Optional[float] = None
    stimulus: Optional[Stimulus] = None
    objects: List[ObjectState] = field(default_factory=list)
    environment: Optional[Environment] = None
    predecessors: List[str] = field(default_factory=list)  # event_ids of preceding events
    secondary_events: List[str] = field(default_factory=list)
    physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5        # how confident the system is in this event


# ---------------------------------------------------------------------------
# Prompt 2, Layer 6 — Event History (Prompt 4 — Causal History)
# ---------------------------------------------------------------------------

@dataclass
class EventHistory:
    """Events that preceded the current event and changed the system state.

    Every event is allowed to have predecessors (Prompt 4).
    Enables: gravity → object moving → rolling → collision → bounce →
    second collision → structural vibration → environmental reflection → decay.
    """
    events: List[AcousticEvent] = field(default_factory=list)
    causal_chain: List[str] = field(default_factory=list)  # ordered event_ids

    def add_event(self, event: AcousticEvent) -> None:
        self.events.append(event)
        self.causal_chain.append(event.event_id)

    def get_predecessors(self, event_id: str) -> List[AcousticEvent]:
        """Get all events that preceded a given event."""
        event = next((e for e in self.events if e.event_id == event_id), None)
        if not event:
            return []
        return [e for e in self.events if e.event_id in event.predecessors]


# ---------------------------------------------------------------------------
# Causal Hypothesis (Prompt 12 — Storyteller's new job)
# ---------------------------------------------------------------------------

@dataclass
class CausalHypothesis:
    """Storyteller's output: an inferred event history behind the user's perception.

    For "a marble hitting rock", this would contain: object material,
    geometry, mass, velocity, impact angle, rock material, rock geometry,
    contact location, environment, surface condition, secondary impacts,
    resonance, propagation, listener position.
    """
    hypothesis_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    perceptual_intent: str = ""
    physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
    event_history: EventHistory = field(default_factory=EventHistory)
    materials: List[MaterialState] = field(default_factory=list)
    objects: List[ObjectState] = field(default_factory=list)
    environment: Environment = field(default_factory=Environment)
    uncertainties: List[str] = field(default_factory=list)
    mechanism_confidence: float = 0.5
    candidate_mechanisms: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Perceptual Specification (Prompt 25 — pipeline entry)
# ---------------------------------------------------------------------------

@dataclass
class PerceptualSpec:
    """Refiner's output: a structured perceptual specification.

    What the user wants to perceive, separated from how to achieve it.
    """
    raw_intent: str = ""
    event_type: str = ""              # impact, scrape, resonance, etc.
    feeling_word: str = ""
    character: List[str] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)
    max_duration_s: float = 1.0
    brightness: Optional[str] = None  # dark, neutral, bright
    density: Optional[str] = None     # sparse, medium, dense
    temperature: Optional[str] = None # warm, neutral, cold
    motion: Optional[str] = None      # rising, falling, arc, flat
    spatial: Optional[str] = None     # close, medium, distant
    material_hint: Optional[str] = None
    environment_hint: Optional[str] = None
    physics_mode: PhysicsMode = PhysicsMode.PLAUSIBLE
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Prompt 7 — Realization = CAUSAL_MODEL + STATE + ENVIRONMENT + SEED
# ---------------------------------------------------------------------------

@dataclass
class Seed:
    """Deterministic seed for reproducible but variable realizations."""
    value: int = field(default_factory=lambda: int(time.time() * 1000) & 0xFFFFFFFF)
    description: str = ""


@dataclass
class Realization:
    """A specific acoustic realization: the concrete output of a generation.

    REALIZATION = CAUSAL_MODEL + STATE + ENVIRONMENT + SEED
    This is a core invariant of Superlarynx (Prompt 7).
    """
    realization_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    hypothesis: Optional[CausalHypothesis] = None
    state: Dict[str, Any] = field(default_factory=dict)
    environment: Environment = field(default_factory=Environment)
    seed: Seed = field(default_factory=Seed)
    # Resolved DSP parameters (the old "recipe" lives here, at the bottom)
    dsp_params: Dict[str, Any] = field(default_factory=dict)
    # Legacy recipe for backward compatibility with existing renderer
    legacy_recipe: Optional[Dict[str, Any]] = None
    # Perceptual signature (filled after analysis, Prompt 22)
    perceptual_signature: Optional[Dict[str, float]] = None
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Prompt 2, Layer 1 — Acoustic Signal
# ---------------------------------------------------------------------------

@dataclass
class AcousticSignal:
    """The actual time-varying waveform produced by the renderer.

    In practice this is an AudioBuffer reference; we store metadata here.
    """
    sample_rate: int = 44100
    channels: int = 2
    duration: float = 0.0
    peak_amplitude: float = 0.0
    rms: float = 0.0


# ---------------------------------------------------------------------------
# Prompt 10 — Evaluation & Feedback
# ---------------------------------------------------------------------------

@dataclass
class PerceptualEvaluation:
    """Multidimensional evaluation of a generated sound (Prompt 10).

    Does not collapse into a single scalar — maintains a multidimensional
    perceptual error vector.
    """
    perceptual_similarity: float = 0.0
    temporal_similarity: float = 0.0
    spectral_similarity: float = 0.0
    transient_similarity: float = 0.0
    roughness: float = 0.0
    brightness: float = 0.0
    density: float = 0.0
    spatial_character: float = 0.0
    decay_behavior: float = 0.0
    material_plausibility: float = 0.0
    causal_plausibility: float = 0.0
    novelty: float = 0.0
    user_preference: float = 0.0  # -1 rejected, 0 neutral, +1 liked
    overall_utility: float = 0.0

    def error_vector(self) -> List[float]:
        """Return the multidimensional error as a list."""
        return [
            self.perceptual_similarity, self.temporal_similarity,
            self.spectral_similarity, self.transient_similarity,
            self.roughness, self.brightness, self.density,
            self.spatial_character, self.decay_behavior,
            self.material_plausibility, self.causal_plausibility,
        ]


# ---------------------------------------------------------------------------
# Prompt 11 — Self-Critique (SABLE's structured output)
# ---------------------------------------------------------------------------

@dataclass
class SableCritique:
    """SABLE's perceptual critique of a realization (Prompt 11, 14).

    Translates measurable acoustic discrepancies into meaningful
    synthesis mutations.
    """
    critique_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    issues: List[str] = field(default_factory=list)
    # e.g. ["too tonal", "transient too clean", "decay too synthetic"]
    mutation_instructions: List[Dict[str, Any]] = field(default_factory=list)
    # e.g. [{"target": "damping", "action": "increase", "amount": 0.2}]
    accept: bool = False
    confidence: float = 0.5
    iteration: int = 0


# ---------------------------------------------------------------------------
# Prompt 2, Layer 7 — Experience (the persistent learning unit)
# ---------------------------------------------------------------------------

@dataclass
class Experience:
    """The complete record of a generation episode.

    The persistent learning unit is EXPERIENCE, not merely a sound file
    or recipe (Prompt 2). This is what Ripwave stores and routes through.
    """
    experience_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    # Input
    user_intent: str = ""
    perceptual_spec: Optional[PerceptualSpec] = None
    # Hypothesis
    causal_hypothesis: Optional[CausalHypothesis] = None
    # Generation
    realization: Optional[Realization] = None
    mechanism_used: str = ""        # which high-level mechanism(s) were used
    # Analysis
    perceptual_signature: Optional[Dict[str, float]] = None
    acoustic_signal: Optional[AcousticSignal] = None
    # Evaluation
    evaluation: Optional[PerceptualEvaluation] = None
    sable_critiques: List[SableCritique] = field(default_factory=list)
    # Mutations
    mutations: List[Dict[str, Any]] = field(default_factory=list)
    mutation_lineage: Optional[str] = None  # parent experience_id
    # Outcome
    outcome: str = ""               # "accepted", "rejected", "tweaked", "abandoned"
    # Context
    context: Dict[str, Any] = field(default_factory=dict)
    # Ripwave metadata (Prompt 8)
    causal_signature: str = ""
    mechanism_signature: str = ""
    material_signature: str = ""
    environment_signature: str = ""
    quality_score: float = 0.0
    novelty_score: float = 0.0
    similarity_cluster: str = ""
    # Timestamps
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def derive_utility(self) -> float:
        """Compute a routing utility score from the evaluation (Prompt 10)."""
        if not self.evaluation:
            return 0.0
        e = self.evaluation
        # Weighted combination — not just preference, but multi-dimensional
        return (
            e.perceptual_similarity * 0.2 +
            e.material_plausibility * 0.15 +
            e.causal_plausibility * 0.15 +
            e.user_preference * 0.3 +
            e.novelty * 0.1 +
            (1.0 - abs(e.brightness)) * 0.05 +
            (1.0 - abs(e.density)) * 0.05
        )


# ---------------------------------------------------------------------------
# Mutation Lineage (Prompt 23)
# ---------------------------------------------------------------------------

@dataclass
class MutationRecord:
    """Track every structural change with attribution (Prompt 23).

    parent → mutation → reason → evaluation → outcome
    Makes the system inspectable rather than mysterious.
    """
    mutation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_experience_id: str = ""
    child_experience_id: str = ""
    mutation_type: str = ""       # parameter | mechanism | routing | topology
    mutation_details: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    evaluation_before: Optional[float] = None
    evaluation_after: Optional[float] = None
    outcome: str = ""             # improved | degraded | neutral | unknown
    timestamp: float = field(default_factory=time.time)
