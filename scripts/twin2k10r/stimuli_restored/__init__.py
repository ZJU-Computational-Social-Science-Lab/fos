# Package marker and public facade for the restored-stimuli deliverable:
# the six withheld experiments (disease, fire_extinguisher, less_is_more,
# seatbelt, sunk_cost, wta_wtp) reintroduced as an isolated add-on to the
# twin2k10r pipeline. Nothing here modifies any frozen file. The names
# re-exported below are the package's whole public surface.
from twin2k10r.stimuli_restored.build_stimuli import (  # noqa: F401
    CATALOG_PATH,
    STIMULI_FILE,
    extract_from_catalog,
    write_stimuli_file,
)
from twin2k10r.stimuli_restored.coverage_audit import (  # noqa: F401
    audit_resolution,
    audit_rows,
    render_audit_markdown,
)
from twin2k10r.stimuli_restored.registry import (  # noqa: F401
    RESTORED_ARMS,
    RESTORED_CONTRASTS,
    RESTORED_EXPERIMENT_NAMES,
    coverage_counts,
    merged_registry,
)
from twin2k10r.stimuli_restored.restored_stimuli import (  # noqa: F401
    restored_stimuli,
)
from twin2k10r.stimuli_restored.scoring import record_outcome  # noqa: F401
