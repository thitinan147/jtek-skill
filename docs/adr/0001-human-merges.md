# ADR-0001: A human merges

- **Status:** accepted
- **Date:** 2026-11-16
- **Deciders:** the maintainers of jtek-skill

## Context

The queue can prepare a branch and a draft PR. Merging that PR ships the change.

## Decision

A human runs `/jt-review` and merges. The agent never writes `merge:` and never runs a merge command. `gate.py merge-queue` only prints the order.

## Consequences

A finished gate is not a release. The human can revert the merge, and can disable an optional self-hosted Unleash flag, without asking the agent to ship again.
