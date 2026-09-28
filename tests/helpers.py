"""Shared test setup: every test runs against throwaway data files."""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import expense_core as core  # noqa: E402

SEED_CSV = (
    "expense_id,amount,category,description,date\n"
    "1,500.0,Food,Trip,2026-01-26\n"
    "2,1000.00,Utilities,home,2026-09-28\n"
)


class DataFilesTestCase(unittest.TestCase):
    """Points core.DATA_FILE / core.HISTORY_FILE at a temp folder seeded with SEED_CSV."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data_file = os.path.join(self.tmp, "expenses.csv")
        self.history_file = os.path.join(self.tmp, "edit_history.csv")
        with open(self.data_file, "w", newline="") as f:
            f.write(SEED_CSV)
        for name, path in (("DATA_FILE", self.data_file), ("HISTORY_FILE", self.history_file)):
            patcher = mock.patch.object(core, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.expenses = core.load_expenses()
        self.history = core.load_history()

    def read_file(self, path):
        with open(path, newline="") as f:
            return f.read()

    def fail_saves(self, message="disk full"):
        """Make the final file swap fail, as a full or read-only disk would."""
        return mock.patch("expense_core.os.replace", side_effect=OSError(message))

    def leftover_temp_files(self):
        return [name for name in os.listdir(self.tmp) if name.endswith(".tmp")]
