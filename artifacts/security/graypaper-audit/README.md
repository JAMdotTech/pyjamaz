# Gray Paper Security Audit

This directory tracks the protocol-first security audit backlog for pyJAMaz against the following authoritative references:

- [Gray Paper PDF](https://graypaper.com/graypaper.pdf)
- [Gray Paper resources index](https://graypaper.com/resources/)
- [Polkadot Wiki: JAM Chain](https://wiki.polkadot.com/learn/learn-jam-chain/)
- [W3F JAM test vectors](https://github.com/w3f/jamtestvectors/)

## Local entrypoint

Run the audit harness from the repo root:

```bash
bash scripts/security_audit.sh --install-python-tools
```

The harness writes scanner output, SBOMs, JUnit XML, and a summary into `artifacts/security/graypaper-audit/output/`. That directory is intentionally ignored except for `.gitkeep`, so generated evidence can be uploaded in CI without polluting commits.

## Tracked audit documents

- `findings.md`: severity-rated engineering backlog with exploit notes and remediation guidance.
- `threat-model.md`: assets, trust boundaries, attack surfaces, and review order.
- `spec-coverage-matrix.md`: security-relevant Gray Paper coverage mapped to code, tests, vectors, and gaps.
- `release-gate.md`: current blocker list and go/no-go criteria.

## Current release posture

The audit is not release-ready yet. Open High-severity blockers remain around QUIC peer authentication and unauthenticated mutating RPC methods.
