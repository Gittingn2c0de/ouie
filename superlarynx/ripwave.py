"""Superlarynx Ripwave Experiential Field — Prompts 8, 9, 15, 16, 17.

Distributed-field memory system adapted from Ripple/Ripwave architecture.
NOT a conventional database — uses distributed-field principles:

  CORE  — active generation / evaluation
  MID   — signal propagation / coordination
  SHELL — experience / learned patterns / routing

Implements multiple interacting memory dimensions (Prompt 9),
exploration vs exploitation routing (Prompt 15),
intelligent forgetting (Prompt 16), and experience clusters (Prompt 17).
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .models import Experience, MutationRecord, PerceptualEvaluation


# ---------------------------------------------------------------------------
# Ripple — the unit of information propagation
# ---------------------------------------------------------------------------

@dataclass
class Ripple:
    """Information about an event/experience propagating through the field.

    Carries structured metadata (Prompt 8).
    """
    ripple_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    experience_id: str = ""
    sound_id: str = ""
    causal_signature: str = ""
    perceptual_signature: Dict[str, float] = field(default_factory=dict)
    mechanism_signature: str = ""
    quality_score: float = 0.0
    confidence: float = 0.5
    physics_mode: str = "plausible"
    seed: int = 0
    material_signature: str = ""
    environment_signature: str = ""
    mutation_history: List[str] = field(default_factory=list)
    novelty: float = 0.5
    similarity_cluster: str = ""
    # Propagation metadata
    origin_locus: str = "core"      # core | mid | shell
    strength: float = 1.0           # decays as ripple propagates
    created_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Experience Cluster (Prompt 17)
# ---------------------------------------------------------------------------

@dataclass
class ExperienceCluster:
    """A cluster of related experiences in the experiential field.

    Clusters are NOT a fixed closed taxonomy — they emerge.
    Each cluster accumulates successful/failed mechanisms, parameter
    distributions, perceptual signatures, and causal signatures.
    """
    cluster_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    label: str = ""                                       # e.g. "impact", "friction", "resonance"
    experience_ids: List[str] = field(default_factory=list)
    successful_mechanisms: List[str] = field(default_factory=list)
    failed_mechanisms: List[str] = field(default_factory=list)
    parameter_distributions: Dict[str, Any] = field(default_factory=dict)
    perceptual_centroid: Dict[str, float] = field(default_factory=dict)
    causal_signatures: List[str] = field(default_factory=list)
    environmental_dependencies: List[str] = field(default_factory=list)
    avg_utility: float = 0.0
    count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def add_experience(self, exp: Experience) -> None:
        self.experience_ids.append(exp.experience_id)
        self.count += 1
        self.last_accessed = time.time()
        if exp.mechanism_used:
            if exp.quality_score > 0.5:
                if exp.mechanism_used not in self.successful_mechanisms:
                    self.successful_mechanisms.append(exp.mechanism_used)
            else:
                if exp.mechanism_used not in self.failed_mechanisms:
                    self.failed_mechanisms.append(exp.mechanism_used)
        # Update running average utility
        self.avg_utility = (
            (self.avg_utility * (self.count - 1) + exp.derive_utility())
            / self.count
        )


# ---------------------------------------------------------------------------
# Memory Dimensions (Prompt 9)
# ---------------------------------------------------------------------------

class MemoryType(Enum):
    CAUSAL = "causal"           # What mechanisms have produced useful results?
    PERCEPTUAL = "perceptual"   # What acoustic signatures → successful outcomes?
    MATERIAL = "material"       # Which material param distributions → desired results?
    ENVIRONMENT = "environment" # Which propagation environments → desired characteristics?
    FAILURE = "failure"         # Which hypotheses repeatedly fail?
    MUTATION = "mutation"       # Which modifications tend to improve specific errors?
    CONTEXT = "context"         # Which mechanisms work for particular description categories?
    NOVELTY = "novelty"         # Which regions of acoustic space are unexplored?


@dataclass
class MemoryEntry:
    """A single entry in a memory dimension."""
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    memory_type: MemoryType = MemoryType.CAUSAL
    key: str = ""                # lookup signature
    value: Dict[str, Any] = field(default_factory=dict)
    utility: float = 0.0
    recency: float = field(default_factory=time.time)
    frequency: int = 1
    outcome_history: List[str] = field(default_factory=list)  # success | failure | neutral
    novelty: float = 0.5
    reproducibility: float = 0.5
    context_diversity: int = 1   # how many different contexts this was useful in
    failure_value: float = 0.0   # how informative this failure is (Prompt 16)

    def survival_score(self) -> float:
        """Compute survival score for intelligent forgetting (Prompt 16).

        A memory's survival depends on: utility, recency, frequency,
        outcome, novelty, reproducibility, context diversity, failure value.
        Importantly, a failed experiment can have HIGH value.
        """
        age = time.time() - self.recency
        recency_factor = math.exp(-age / (86400 * 7))  # 7-day half-life
        return (
            self.utility * 0.25 +
            recency_factor * 0.15 +
            min(self.frequency / 10.0, 1.0) * 0.10 +
            self.novelty * 0.10 +
            self.reproducibility * 0.10 +
            min(self.context_diversity / 5.0, 1.0) * 0.10 +
            self.failure_value * 0.20  # High-information failures preserved
        )


# ---------------------------------------------------------------------------
# Ripwave Field (the main experiential memory)
# ---------------------------------------------------------------------------

class RipwaveField:
    """The Ripwave experiential field (Prompts 8, 9, 15, 16, 17).

    Distributed-field memory that learns not merely "this sound was good"
    but "this family of mechanisms tends to solve this class of
    perceptual target."

    Structure:
        CORE  — active generation / evaluation
        MID   — signal propagation / coordination
        SHELL — experience / learned patterns / routing
    """

    def __init__(self, max_experiences: int = 500,
                 max_memories_per_type: int = 200):
        # Experience storage
        self.experiences: Dict[str, Experience] = {}
        self.max_experiences = max_experiences

        # Memory dimensions (Prompt 9)
        self.memories: Dict[MemoryType, Dict[str, MemoryEntry]] = {
            mt: {} for mt in MemoryType
        }
        self.max_memories_per_type = max_memories_per_type

        # Experience clusters (Prompt 17)
        self.clusters: Dict[str, ExperienceCluster] = {}

        # Ripple propagation log
        self.ripples: List[Ripple] = []
        self.max_ripples = 1000

        # Mutation lineage
        self.mutations: List[MutationRecord] = []

        # Exploration/exploitation state (Prompt 15)
        self.exploration_pressure: float = 0.3
        self.exploitation_pressure: float = 0.7
        self.consecutive_poor_results: int = 0

    # -- Core operations --

    def store_experience(self, exp: Experience) -> None:
        """Store a new experience in the field."""
        self.experiences[exp.experience_id] = exp

        # Create ripple
        ripple = Ripple(
            experience_id=exp.experience_id,
            causal_signature=exp.causal_signature,
            perceptual_signature=exp.perceptual_signature or {},
            mechanism_signature=exp.mechanism_signature,
            quality_score=exp.quality_score,
            material_signature=exp.material_signature,
            environment_signature=exp.environment_signature,
            novelty=exp.novelty_score,
            similarity_cluster=exp.similarity_cluster,
        )
        self._propagate_ripple(ripple)

        # Update memory dimensions
        self._update_memories(exp)

        # Assign to cluster
        self._assign_to_cluster(exp)

        # Track exploration/exploitation
        if exp.evaluation and exp.evaluation.user_preference < 0:
            self.consecutive_poor_results += 1
        else:
            self.consecutive_poor_results = 0

        # Intelligent forgetting
        if len(self.experiences) > self.max_experiences:
            self._forget()

    def _propagate_ripple(self, ripple: Ripple) -> None:
        """Propagate a ripple through the field (Prompt 8)."""
        self.ripples.append(ripple)
        if len(self.ripples) > self.max_ripples:
            self.ripples = self.ripples[-self.max_ripples:]

    def _update_memories(self, exp: Experience) -> None:
        """Update all memory dimensions from a new experience (Prompt 9)."""
        utility = exp.derive_utility()
        is_success = exp.outcome in ("accepted", "liked")
        is_failure = exp.outcome in ("rejected", "abandoned")

        # Causal memory
        if exp.causal_signature:
            self._update_memory_entry(
                MemoryType.CAUSAL, exp.causal_signature,
                {"mechanism": exp.mechanism_used, "utility": utility},
                utility, is_success, is_failure,
            )

        # Perceptual memory
        if exp.perceptual_signature:
            sig_key = self._signature_key(exp.perceptual_signature)
            self._update_memory_entry(
                MemoryType.PERCEPTUAL, sig_key,
                {"signature": exp.perceptual_signature, "utility": utility},
                utility, is_success, is_failure,
            )

        # Material memory
        if exp.material_signature:
            self._update_memory_entry(
                MemoryType.MATERIAL, exp.material_signature,
                {"mechanism": exp.mechanism_used, "utility": utility},
                utility, is_success, is_failure,
            )

        # Environment memory
        if exp.environment_signature:
            self._update_memory_entry(
                MemoryType.ENVIRONMENT, exp.environment_signature,
                {"mechanism": exp.mechanism_used, "utility": utility},
                utility, is_success, is_failure,
            )

        # Failure memory — distinguish low-value vs high-information failures
        if is_failure:
            failure_value = self._compute_failure_value(exp)
            self._update_memory_entry(
                MemoryType.FAILURE, exp.mechanism_signature or exp.mechanism_used,
                {
                    "hypothesis": exp.causal_signature,
                    "error": exp.evaluation.error_vector() if exp.evaluation else [],
                    "failure_value": failure_value,
                },
                failure_value, False, True,
            )

        # Mutation memory
        if exp.mutations:
            for mut in exp.mutations:
                mut_key = str(mut.get("type", "")) + ":" + str(mut.get("target", ""))
                self._update_memory_entry(
                    MemoryType.MUTATION, mut_key,
                    {"mutation": mut, "utility": utility},
                    utility, is_success, is_failure,
                )

        # Context memory
        if exp.user_intent:
            context_key = self._context_signature(exp.user_intent)
            self._update_memory_entry(
                MemoryType.CONTEXT, context_key,
                {"mechanism": exp.mechanism_used, "utility": utility},
                utility, is_success, is_failure,
            )

        # Novelty memory — track explored regions
        if exp.mechanism_signature:
            if exp.mechanism_signature not in self.memories[MemoryType.NOVELTY]:
                self._update_memory_entry(
                    MemoryType.NOVELTY, exp.mechanism_signature,
                    {"first_seen": time.time(), "count": 1},
                    0.5, is_success, is_failure,
                )
            else:
                entry = self.memories[MemoryType.NOVELTY][exp.mechanism_signature]
                entry.frequency += 1
                entry.novelty = max(0.0, entry.novelty - 0.05)

    def _update_memory_entry(
        self, mem_type: MemoryType, key: str,
        value: Dict[str, Any], utility: float,
        is_success: bool, is_failure: bool,
    ) -> None:
        """Update or create a memory entry."""
        store = self.memories[mem_type]
        if key in store:
            entry = store[key]
            entry.frequency += 1
            entry.recency = time.time()
            entry.utility = (entry.utility * 0.7 + utility * 0.3)  # EMA
            entry.outcome_history.append("success" if is_success else "failure" if is_failure else "neutral")
            entry.outcome_history = entry.outcome_history[-20:]  # keep last 20
            if is_failure:
                entry.failure_value = max(entry.failure_value, value.get("failure_value", 0.0))
        else:
            entry = MemoryEntry(
                memory_type=mem_type,
                key=key,
                value=value,
                utility=utility,
                outcome_history=["success" if is_success else "failure" if is_failure else "neutral"],
                failure_value=value.get("failure_value", 0.0) if is_failure else 0.0,
            )
            store[key] = entry

        # Enforce limit with intelligent forgetting
        if len(store) > self.max_memories_per_type:
            self._forget_from_memory(mem_type)

    def _compute_failure_value(self, exp: Experience) -> float:
        """Distinguish low-value failure from high-information failure (Prompt 16).

        "This mechanism consistently fails for metallic impacts but succeeds
        for hollow wooden impacts" — that is useful knowledge.
        """
        if not exp.evaluation:
            return 0.1
        error_vec = exp.evaluation.error_vector()
        # High-information failures have specific, consistent error patterns
        error_variance = sum((e - sum(error_vec) / max(len(error_vec), 1)) ** 2
                             for e in error_vec) / max(len(error_vec), 1)
        # Low variance = consistent failure pattern = more informative
        specificity = 1.0 - min(error_variance, 1.0)
        return specificity * 0.8 + 0.2  # minimum 0.2 info value

    def _assign_to_cluster(self, exp: Experience) -> None:
        """Assign experience to an existing or new cluster (Prompt 17)."""
        best_cluster = None
        best_score = 0.0

        for cluster in self.clusters.values():
            score = self._cluster_similarity(exp, cluster)
            if score > best_score and score > 0.3:
                best_score = score
                best_cluster = cluster

        if best_cluster:
            best_cluster.add_experience(exp)
            exp.similarity_cluster = best_cluster.cluster_id
        else:
            # Create new emergent cluster
            new_cluster = ExperienceCluster(
                label=exp.mechanism_used or exp.causal_signature or "unknown",
            )
            new_cluster.add_experience(exp)
            self.clusters[new_cluster.cluster_id] = new_cluster
            exp.similarity_cluster = new_cluster.cluster_id

    def _cluster_similarity(self, exp: Experience,
                            cluster: ExperienceCluster) -> float:
        """Compute similarity between an experience and a cluster."""
        score = 0.0
        if exp.mechanism_used in cluster.successful_mechanisms:
            score += 0.3
        if exp.causal_signature in cluster.causal_signatures:
            score += 0.3
        # Perceptual signature distance
        if exp.perceptual_signature and cluster.perceptual_centroid:
            shared_keys = set(exp.perceptual_signature) & set(cluster.perceptual_centroid)
            if shared_keys:
                dist = sum(
                    (exp.perceptual_signature[k] - cluster.perceptual_centroid[k]) ** 2
                    for k in shared_keys
                ) / len(shared_keys)
                score += max(0.0, 0.4 * (1.0 - dist))
        return score

    # -- Routing (Prompt 15) --

    def route(self, perceptual_target: Dict[str, Any],
              causal_signature: str = "",
              context: str = "") -> Dict[str, Any]:
        """Route a new generation request using memory (Prompt 15).

        Balances exploration vs exploitation:
          - High confidence + familiar target → exploit
          - Low confidence + novel target → explore
          - Repeated convergence + poor evaluation → force exploration

        User intent always wins over system habits (Prompt 24).
        """
        routing = {
            "mode": "explore",      # explore | exploit
            "suggested_mechanisms": [],
            "avoid_mechanisms": [],
            "parameter_hints": {},
            "cluster_id": "",
            "confidence": 0.0,
            "novelty": 1.0,
        }

        # Check if we have causal memory matches
        causal_matches = []
        if causal_signature and causal_signature in self.memories[MemoryType.CAUSAL]:
            entry = self.memories[MemoryType.CAUSAL][causal_signature]
            causal_matches.append(entry)
            routing["confidence"] = max(routing["confidence"], entry.utility)

        # Check context memory
        if context:
            ctx_key = self._context_signature(context)
            if ctx_key in self.memories[MemoryType.CONTEXT]:
                entry = self.memories[MemoryType.CONTEXT][ctx_key]
                if entry.value.get("mechanism"):
                    routing["suggested_mechanisms"].append(entry.value["mechanism"])
                routing["confidence"] = max(routing["confidence"],
                                            entry.utility * 0.8)

        # Check failure memory — avoid known bad mechanisms
        for key, entry in self.memories[MemoryType.FAILURE].items():
            if entry.frequency >= 3 and entry.utility < 0.3:
                routing["avoid_mechanisms"].append(key)

        # Check novelty
        novelty_entries = self.memories[MemoryType.NOVELTY]
        if causal_signature and causal_signature in novelty_entries:
            routing["novelty"] = novelty_entries[causal_signature].novelty
        else:
            routing["novelty"] = 1.0  # completely novel

        # Decision: explore vs exploit (Prompt 15)
        if self.consecutive_poor_results >= 3:
            # Force exploration — system is stuck
            routing["mode"] = "explore"
            routing["confidence"] *= 0.5
        elif routing["confidence"] > 0.7 and routing["novelty"] < 0.3:
            # Familiar territory, known good solution → exploit
            routing["mode"] = "exploit"
        elif routing["novelty"] > 0.7 or routing["confidence"] < 0.3:
            # Novel territory or low confidence → explore
            routing["mode"] = "explore"
        else:
            # Mixed — balance
            routing["mode"] = "exploit" if routing["confidence"] > routing["novelty"] else "explore"

        # Find best cluster
        if causal_signature:
            for cid, cluster in self.clusters.items():
                if causal_signature in cluster.causal_signatures:
                    routing["cluster_id"] = cid
                    routing["suggested_mechanisms"].extend(cluster.successful_mechanisms)
                    break

        return routing

    # -- Forgetting (Prompt 16) --

    def _forget(self) -> None:
        """Intelligent forgetting — not solely by age (Prompt 16)."""
        if len(self.experiences) <= self.max_experiences:
            return
        # Score all experiences
        scored = []
        for eid, exp in self.experiences.items():
            score = self._experience_survival_score(exp)
            scored.append((score, eid))
        scored.sort()  # lowest survival score first
        # Remove bottom 10%
        to_remove = max(1, len(scored) // 10)
        for _, eid in scored[:to_remove]:
            del self.experiences[eid]

    def _experience_survival_score(self, exp: Experience) -> float:
        """Survival score based on utility, recency, novelty, etc."""
        age = time.time() - exp.created_at
        recency = math.exp(-age / (86400 * 30))  # 30-day half-life
        utility = exp.derive_utility()
        novelty = exp.novelty_score
        return utility * 0.35 + recency * 0.20 + novelty * 0.15 + 0.30

    def _forget_from_memory(self, mem_type: MemoryType) -> None:
        """Remove lowest-survival entries from a memory dimension."""
        store = self.memories[mem_type]
        if len(store) <= self.max_memories_per_type:
            return
        scored = [(entry.survival_score(), key) for key, entry in store.items()]
        scored.sort()
        to_remove = max(1, len(scored) // 10)
        for _, key in scored[:to_remove]:
            del store[key]

    # -- BREATHE inspection (Prompt 13) --

    def breathe_inspect(self) -> Dict[str, Any]:
        """BREATHE adaptive-systems review of the field (Prompt 13).

        Checks whether the field is becoming too centralized, brittle,
        repetitive, or dependent on one fixed route.
        """
        report: Dict[str, Any] = {
            "total_experiences": len(self.experiences),
            "total_clusters": len(self.clusters),
            "warnings": [],
            "recommendations": [],
        }

        # Check cluster concentration
        if self.clusters:
            sizes = [c.count for c in self.clusters.values()]
            max_size = max(sizes)
            if max_size > sum(sizes) * 0.5:
                report["warnings"].append(
                    f"Cluster concentration: one cluster has {max_size}/{sum(sizes)} experiences"
                )
                report["recommendations"].append("Force exploration into underrepresented clusters")

        # Check mechanism diversity
        all_mechanisms = set()
        for exp in self.experiences.values():
            if exp.mechanism_used:
                all_mechanisms.add(exp.mechanism_used)
        if len(all_mechanisms) < 3 and len(self.experiences) > 20:
            report["warnings"].append(
                f"Low mechanism diversity: only {len(all_mechanisms)} mechanisms used"
            )
            report["recommendations"].append("Increase exploration pressure")

        # Check failure rate
        recent = [e for e in self.experiences.values()
                  if time.time() - e.created_at < 3600]
        if recent:
            fail_rate = sum(1 for e in recent if e.outcome == "rejected") / len(recent)
            if fail_rate > 0.7:
                report["warnings"].append(f"High recent failure rate: {fail_rate:.0%}")
                report["recommendations"].append("Review routing — may be stuck in a rut")

        # Check exploration pressure
        if self.consecutive_poor_results > 5:
            report["warnings"].append("Extended poor results streak")
            report["recommendations"].append("Reset exploration parameters")

        return report

    # -- Utility helpers --

    @staticmethod
    def _signature_key(sig: Dict[str, float]) -> str:
        """Create a compact key from a perceptual signature for lookup."""
        if not sig:
            return "empty"
        # Quantize to reduce near-duplicate keys
        parts = []
        for k in sorted(sig.keys())[:5]:
            parts.append(f"{k}:{sig[k]:.1f}")
        return "|".join(parts)

    @staticmethod
    def _context_signature(text: str) -> str:
        """Create a rough context key from user text."""
        words = text.lower().split()
        # Keep up to 4 most "meaningful" words (skip articles etc)
        skip = {"a", "an", "the", "of", "in", "on", "at", "to", "and", "or", "is", "it", "i"}
        meaningful = [w for w in words if w not in skip][:4]
        return "|".join(sorted(meaningful)) if meaningful else "generic"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the field for persistence."""
        return {
            "experiences_count": len(self.experiences),
            "clusters_count": len(self.clusters),
            "memories": {
                mt.value: len(entries) for mt, entries in self.memories.items()
            },
            "exploration_pressure": self.exploration_pressure,
            "exploitation_pressure": self.exploitation_pressure,
            "consecutive_poor_results": self.consecutive_poor_results,
        }
