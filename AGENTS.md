# AGENTS.md

## Roles defined for this repository

### Pipeline Engineer
- **Scope**: Implements deterministic logic for Stage 1 (rule extraction), Stage 3 (golden‑dataset mining), and Stage 4 (divergence verification).
- **Responsibilities**:
  - Write and maintain Python scripts that read structured data, perform calculations, and output JSON/`.dat` files.
  - Ensure the pipeline is reproducible, config‑driven and free of hard‑coded paths.
  - Manage COBOL variant generation and compilation (Stage 2 ablation support).
  - Keep documentation, configuration (`pipeline_config.yaml`) and ignore rules up‑to‑date.

### Provenance Analyst
- **Scope**: Handles Stage 2 – document‑matching and provenance extraction.
- **Responsibilities**:
  - Run `recover_provenance.py` to map rule identifiers to their source documentation.
  - Curate the `RISK_NARRATIVES` table and maintain the provenance JSON output.
  - Verify that modern‑side processing aligns with legacy documentation.
  - Work closely with the Pipeline Engineer to ensure both stages integrate cleanly.

Both roles collaborate to deliver a fully‑automated migration pipeline that:
1. Extracts rule definitions from COBOL source.
2. Recovers provenance information.
3. Mines a golden dataset of historic claims.
4. Generates compiled COBOL ablation variants and verifies divergence.

The repository contains no user‑specific session data; all artefacts are generated on demand.
