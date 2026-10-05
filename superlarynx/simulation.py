"""Superlarynx Simulation Interface — Prompt 21.

Clean interface for external simulation experiments.
Allows Google Colab / Python / GPU simulation to become an experimental
laboratory rather than a required runtime dependency.

Reduced-order models are the default.
High-fidelity simulation is invoked when the perceptual target benefits from it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SimulationRequest:
    """Input to an external simulation module (Prompt 21).

    A simulation module receives material parameters, geometry, initial
    conditions, environment, stimulus, duration, and resolution.
    """
    material_params: Dict[str, float] = field(default_factory=dict)
    geometry: str = ""
    initial_conditions: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    stimulus: Dict[str, Any] = field(default_factory=dict)
    duration: float = 1.0         # seconds
    resolution: int = 44100       # samples per second
    solver: str = "reduced_order" # reduced_order | modal | fdtd | fem


@dataclass
class SimulationResult:
    """Output from a simulation module.

    Returns time-domain signal, modal information, energy decay,
    contact forces, state trajectories, and derived acoustic features.
    """
    signal: List[float] = field(default_factory=list)        # time-domain samples
    sample_rate: int = 44100
    modal_frequencies: List[float] = field(default_factory=list)
    modal_amplitudes: List[float] = field(default_factory=list)
    modal_decays: List[float] = field(default_factory=list)
    energy_decay: List[float] = field(default_factory=list)  # energy over time
    contact_forces: List[float] = field(default_factory=list)
    state_trajectory: List[Dict[str, float]] = field(default_factory=list)
    acoustic_features: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SimulationInterface:
    """Interface for plugging in external physics simulations.

    This creates a clean boundary: the core Superlarynx engine works
    without any simulation backend. Simulations are optional experiments
    that can refine the reduced-order models.
    """

    def __init__(self):
        self._backends: Dict[str, Any] = {}

    def register_backend(self, name: str, backend: Any) -> None:
        """Register an external simulation backend (e.g., Python FEM solver)."""
        self._backends[name] = backend

    def simulate(self, request: SimulationRequest) -> SimulationResult:
        """Run a simulation. Falls back to reduced-order model if no backend.

        Args:
            request: Simulation parameters.

        Returns:
            SimulationResult with signal and analysis data.
        """
        if request.solver in self._backends:
            backend = self._backends[request.solver]
            return backend.run(request)

        # Default: reduced-order modal synthesis
        return self._reduced_order_simulate(request)

    def _reduced_order_simulate(self, req: SimulationRequest) -> SimulationResult:
        """Built-in reduced-order modal simulation.

        Computes a simple modal decomposition from material parameters.
        Not physically rigorous, but sufficient for rapid iteration.
        """
        sr = req.resolution
        n_samples = int(req.duration * sr)

        # Estimate modal frequencies from material params
        density = req.material_params.get("density", 2000)
        elasticity = req.material_params.get("elasticity", 0.5)
        mass = req.material_params.get("mass", 0.1)
        damping = req.material_params.get("damping", 0.3)

        # Simple modal estimation
        base_freq = 100 + (elasticity * 2000) / max(0.01, mass ** 0.5)
        n_modes = max(1, min(8, int(5 * (1 - damping))))

        modal_freqs = []
        modal_amps = []
        modal_decays = []

        for i in range(n_modes):
            ratio = [1.0, 2.37, 4.12, 6.58, 9.92, 14.2, 19.4, 25.8][i] if i < 8 else (i + 1) * 2
            freq = base_freq * ratio
            if freq > sr / 2:
                break
            modal_freqs.append(freq)
            modal_amps.append(1.0 / (1 + i * 0.5))
            modal_decays.append((0.02 + (1 - damping) * 0.3) / (1 + i * 0.3))

        # Synthesize
        signal = [0.0] * n_samples
        energy_decay = []

        for i, (freq, amp, decay) in enumerate(zip(modal_freqs, modal_amps, modal_decays)):
            for s in range(n_samples):
                t = s / sr
                env = amp * math.exp(-t / max(0.001, decay))
                signal[s] += env * math.sin(2 * math.pi * freq * t)

        # Normalize
        peak = max(abs(s) for s in signal) if signal else 1.0
        if peak > 0:
            signal = [s / peak * 0.9 for s in signal]

        # Compute energy decay curve
        window = sr // 100
        for i in range(0, n_samples - window, window):
            chunk = signal[i:i + window]
            rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
            energy_decay.append(rms)

        return SimulationResult(
            signal=signal,
            sample_rate=sr,
            modal_frequencies=modal_freqs,
            modal_amplitudes=modal_amps,
            modal_decays=modal_decays,
            energy_decay=energy_decay,
            acoustic_features={
                "base_frequency": base_freq,
                "n_modes": len(modal_freqs),
                "estimated_decay_time": modal_decays[0] if modal_decays else 0.1,
            },
        )


# Singleton interface
simulation_interface = SimulationInterface()
