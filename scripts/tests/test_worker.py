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
