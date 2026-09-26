"""Stop an active batch and clear its workspace once the worker releases it."""

import time

from r3el.interface.WorkspaceDb import WorkspaceDb, WorkspaceBusy


class ClearWorkspace:
    def __init__(self, workspace: WorkspaceDb) -> None:
        self._workspace = workspace

    def run(self, batch_id: str) -> None:
        # This also prevents a matching worker from starting its next item.
        self._workspace.request_stop(batch_id, matching=True)
        while True:
            try:
                self._workspace.clear(batch_id)
                return
            except WorkspaceBusy:
                time.sleep(0.2)
