"""Keep postmatch navigation and widget state coherent after a successful delivery."""
from __future__ import annotations


def clear_submitted_report_state(state, report_id: int) -> None:
    rid = int(report_id)
    prefixes = (
        f"eval33_{rid}_", f"eval_saved_snapshot_34_{rid}_",
        f"eval_dirty_34_{rid}_", f"only_pending_341_{rid}_",
        f"save_status_{rid}_",
    )
    exact = {
        f"report_workspace_33_{rid}", f"report_stage_{rid}", f"confirm_submit_38_{rid}",
        f"readonly_report_section_{rid}",
    }
    for key in tuple(state):
        if isinstance(key, str) and (key in exact or key.startswith(prefixes)):
            state.pop(key, None)
