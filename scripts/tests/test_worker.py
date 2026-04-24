# scripts/tests/test_worker.py
import asyncio
from unittest.mock import MagicMock, patch

import pytest


class TestLogGatherResults:
    def test_logs_exceptions_but_does_not_raise(self):
        from worker import log_gather_results

        mock_log = MagicMock()
        results = [None, ValueError("boom"), None, RuntimeError("also boom")]
        claimed = [
            {"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"},
        ]

        log_gather_results(results, claimed, logger=mock_log)

        # Two errors logged
        assert mock_log.call_count == 2
        # The error messages reference the run IDs
        logged = " ".join(str(c.args[0]) for c in mock_log.call_args_list)
        assert "b" in logged
        assert "d" in logged
        assert "boom" in logged


from worker import _fire_merge_pass_if_bulk_complete


class TestFireMergePassIfBulkComplete:
    def test_does_not_fire_when_pending_remain(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.in_.return_value.\
            execute.return_value.data = [{"id": "still-running"}]

        _fire_merge_pass_if_bulk_complete(sb, bulk_import_id="b1", workspace_id="w1")
        sb.rpc.assert_not_called()

    def test_fires_when_bulk_terminal(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.in_.return_value.\
            execute.return_value.data = []
        sb.rpc.return_value.execute.return_value = None

        _fire_merge_pass_if_bulk_complete(sb, bulk_import_id="b1", workspace_id="w1")
        sb.rpc.assert_called_once_with(
            "run_cross_workspace_merge_pass",
            {"p_workspace_id": "w1", "p_bulk_import_id": "b1"},
        )

    def test_swallows_rpc_errors(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.in_.return_value.\
            execute.return_value.data = []
        sb.rpc.return_value.execute.side_effect = Exception("rpc failed")

        _fire_merge_pass_if_bulk_complete(sb, bulk_import_id="b1", workspace_id="w1")
        # Should not raise.
