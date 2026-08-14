# Phase 16 Performance Baseline

## Purpose
This document establishes the official performance baseline metrics for the Autonomous Website Generation Engine. Future regressions will be measured against these latencies.

## Baseline Metrics
- **Generation Throughput**: 1 completed session / ~5.2 seconds average (single thread execution)
- **Average Total Generation Latency**: ~5,200 ms
- **Provider Latency (average external bound)**: ~3,000 ms per provider hit
- **Ranking Latency**: < 5 ms per 50 payloads
- **Persistence Latency (Odoo ORM create bounds)**: ~150 ms 
- **Optimization Latency (AST operations)**: ~20 ms
- **Validation Latency**: ~25 ms
- **Preview Latency (Node rendering mapping)**: < 15 ms

## Benchmarking Rules
Any future update to Phase 16 architecture that degrades these baseline latency profiles by greater than 10% will be considered a failed regression.
