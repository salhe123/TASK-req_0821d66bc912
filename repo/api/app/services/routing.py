"""Sticky hash-based A/B routing.

Bucket calculation:
  bucket = int(sha256(subject_key)[:8], 16) % 100

Routing:
  - If weight_a + weight_b != 100 the caller is responsible; we route by bucket
    < weight_a → A, else B (bucket is 0..99, so weight_a = N means buckets 0..N-1 are A).

Stickiness property: a given subject with bucket b lands on arm A whenever
weight_a > b (i.e., weight_a ∈ [b+1, 100]), and on arm B when weight_a ≤ b.
So shifting weight_a only changes arms for subjects whose bucket falls at the
threshold — all other subjects stay sticky.
"""
from __future__ import annotations

import hashlib


def bucket_for(subject_key: str) -> int:
    h = hashlib.sha256(subject_key.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 100


def pick_arm(subject_key: str, weight_a: int) -> str:
    b = bucket_for(subject_key)
    return "A" if b < weight_a else "B"
