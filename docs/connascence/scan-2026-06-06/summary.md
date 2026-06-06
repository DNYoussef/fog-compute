# Connascence Scan Summary

- Project: `fog-compute`
- Path: `D:\Projects\fog-compute`
- Git branch: `main`
- Git commit: `20e4d530bcc48ef6357835c991e2eec339a48edc`
- Dirty before scan: `True`
- Scan succeeded: `True`
- Python files staged: `320`

## Commands Run
- `C:\Python312\python.exe -m analyzer C:\Users\17175\Desktop\_SCRATCH\connascence-portfolio-scan-2026-06-06\raw-results\fog-compute\mirror --format json --output C:\Users\17175\Desktop\_SCRATCH\connascence-portfolio-scan-2026-06-06\raw-results\fog-compute\connascence.raw.json --no-duplication --compliance-threshold 0 --max-god-objects 999999` (exit 0)
- `connascence_portfolio_runner.py generate-sarif-from-json D:\Projects\fog-compute\docs\connascence\scan-2026-06-06\connascence.json` (exit 0)
- `C:\Python312\python.exe -m analyzer.ast_engine --path C:\Users\17175\Desktop\_SCRATCH\connascence-portfolio-scan-2026-06-06\raw-results\fog-compute\mirror --analyzer god_object --output C:\Users\17175\Desktop\_SCRATCH\connascence-portfolio-scan-2026-06-06\raw-results\fog-compute\god-object.raw.json` (exit 0)

## Counts By Severity

- low: 11235
- medium: 1142
- critical: 101
- high: 42

## Counts By Type

- connascence_of_meaning: 10020
- CoV: 1078
- connascence_of_convention: 448
- connascence_of_type: 304
- connascence_of_execution: 217
- CoP: 148
- connascence_of_timing: 136
- god_object: 98
- connascence_of_algorithm: 67
- CoA: 4

## Top Files

- `D:\Projects\fog-compute\src\idle\mobile_resource_manager.py`: 429
- `D:\Projects\fog-compute\src\p2p\unified_p2p_system.py`: 335
- `D:\Projects\fog-compute\tools\lib\validation\quality_validator.py`: 279
- `D:\Projects\fog-compute\backend\server\models\database.py`: 245
- `D:\Projects\fog-compute\src\idle\edge_manager.py`: 228
- `D:\Projects\fog-compute\backend\pipeline\ai_handlers.py`: 216
- `D:\Projects\fog-compute\src\fog\benchmarks\benchmark_suite.py`: 216
- `D:\Projects\fog-compute\backend\server\routes\fog_bridge.py`: 205
- `D:\Projects\fog-compute\src\tokenomics\unified_dao_tokenomics_system.py`: 183
- `D:\Projects\fog-compute\backend\server\routes\deployment.py`: 172

## Top 10 Actionable Findings

1. `D:\Projects\fog-compute\tools\lib\validation\spec_validation.py:930` - Class 'ImplementationPlanValidator' is a God Object (test context): Very low cohesion (0.29)
2. `D:\Projects\fog-compute\tools\lib\validation\quality_validator.py:297` - Class 'QualityValidator' is a God Object: 21 methods, ~565 lines
3. `D:\Projects\fog-compute\src\vpn\transports\betanet_transport.py:60` - Class 'BetanetTransport' is a God Object (config context): Very low cohesion (0.22)
4. `D:\Projects\fog-compute\src\vpn\onion_routing.py:156` - Class 'OnionRouter' is a God Object (api_controller context): Very low cohesion (0.28)
5. `D:\Projects\fog-compute\src\vpn\onion_circuit_service.py:53` - Class 'OnionCircuitService' is a God Object (config context): Very low cohesion (0.27)
6. `D:\Projects\fog-compute\src\vpn\fog_onion_coordinator.py:170` - Class 'FogOnionCoordinator' is a God Object (unknown context): Very low cohesion (0.21)
7. `D:\Projects\fog-compute\src\tokenomics\unified_dao_tokenomics_system.py:242` - Class 'TokenDatabase' is a God Object (config context): Very low cohesion (0.10)
8. `D:\Projects\fog-compute\src\tokenomics\unified_dao_tokenomics_system.py:555` - Class 'UnifiedDAOTokenomicsSystem' is a God Object (config context): Very low cohesion (0.16)
9. `D:\Projects\fog-compute\src\tokenomics\tokenomics_integration.py:134` - Class 'TokenomicsIntegration' is a God Object (unknown context): Very low cohesion (0.23)
10. `D:\Projects\fog-compute\src\tokenomics\fog_tokenomics_service.py:19` - Class 'FogTokenomicsService' is a God Object (unknown context): Very low cohesion (0.26)

## Tool Limitations

- Connascence currently analyzes Python files only; non-Python coupling is not covered.
- Source-bearing fields and literal values were stripped or redacted before writing artifacts.
- Excluded directories and sensitive data patterns were not staged into the scan mirror.

## Next Cleanup Recommendations

### 1. Quick Wins
- Add type annotations at public function boundaries with the highest CoT counts.
- Replace repeated or magic literals with named constants or configuration keys.

### 2. Medium Refactors
- Convert high-parameter functions to keyword-only APIs or parameter objects.
- Split complex functions and consolidate duplicated algorithmic branches.
- Start with the top files by violation count and keep each change behavior-preserving.

### 3. Large Architectural Work
- Split god objects into cohesive classes around stable domain responsibilities.
- Use module or service boundaries to isolate recurring high-count hotspots.
