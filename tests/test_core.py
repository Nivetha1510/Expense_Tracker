import os
import subprocess
import sys
import tempfile
from decimal import Decimal

import expense_core as core
from tests.helpers import DataFilesTestCase, SEED_CSV


class ParseAmountTests(DataFilesTestCase):
    def test_accepts_positive_amounts_with_up_to_two_decimals(self):
        for raw, expected in [("12", "12.00"), ("12.5", "12.50"), ("0.01", "0.01"),
                              (" 7.25 ", "7.25"), (3.25, "3.25"), (Decimal("1.10"), "1.10")]:
            self.assertEqual(str(core.parse_amount(raw)), expected)

    def test_rejects_invalid_amounts(self):
        for bad in ["nan", "NaN", "inf", "-Infinity", "0.001", "1.005", "1e-3",
                    "0", "0.00", "-5", "abc", "", float("nan"), float("inf")]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    core.parse_amount(bad)

    def test_tiny_amount_is_rejected_not_rounded_to_zero(self):
        ok, message = core.add_expense(self.expenses, "0.001", "Food", "x")
        self.assertFalse(ok)
        self.assertIn("2 decimal places", message)
        self.assertEqual(len(self.expenses), 2)

    def test_rejects_absurdly_large_amount(self):
        with self.assertRaises(ValueError):
            core.parse_amount("1e999999")


class LoadingTests(DataFilesTestCase):
    def test_existing_csv_loads_as_decimals(self):
        self.assertEqual(self.expenses[0]["amount"], Decimal("500.0"))
        self.assertEqual(core.total_spent(self.expenses), Decimal("1500.00"))

    def test_loading_never_changes_the_file(self):
        core.load_expenses()
        self.assertEqual(self.read_file(self.data_file), SEED_CSV)

    def test_legacy_extra_column_is_ignored(self):
        with open(self.data_file, "w", newline="") as f:
            f.write("expense_id,amount,category,description,date,updated_at\n"
                    "1,5.00,Food,Trip,2026-01-26,2026-09-28 10:00:00\n")
        loaded = core.load_expenses()
        self.assertEqual(list(loaded[0]), core.EXPENSE_FIELDS)

    def test_unreadable_data_raises_instead_of_starting_fresh(self):
        with open(self.data_file, "w", newline="") as f:
            f.write("expense_id,amount,category,description,date\n1,nan,Food,x,2026-01-01\n")
        with self.assertRaises(core.DataFileError):
            core.load_expenses()
        with open(self.data_file, "w", newline="") as f:
            f.write("wrong,header\n1,2\n")
        with self.assertRaises(core.DataFileError):
            core.load_expenses()

    def test_default_paths_do_not_depend_on_the_working_directory(self):
        project = os.path.dirname(os.path.abspath(core.__file__))
        code = f"import sys; sys.path.insert(0, {project!r}); import expense_core as c; print(c.DATA_FILE); print(c.HISTORY_FILE)"
        out = subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(),
                             capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertEqual(out[0], os.path.join(project, "expenses.csv"))
        self.assertEqual(out[1], os.path.join(project, "edit_history.csv"))


class AddExpenseTests(DataFilesTestCase):
    def test_add_persists_and_normalizes_date(self):
        ok, _ = core.add_expense(self.expenses, "4.20", " food ", " lunch ", "2026-3-5")
        self.assertTrue(ok)
        reloaded = core.load_expenses()
        self.assertEqual(reloaded[-1]["amount"], Decimal("4.20"))
        self.assertEqual(reloaded[-1]["category"], "Food")
        self.assertEqual(reloaded[-1]["description"], "lunch")
        self.assertEqual(reloaded[-1]["date"], "2026-03-05")

    def test_invalid_date_rejected(self):
        ok, message = core.add_expense(self.expenses, "5", "Food", "x", "2026-13-40")
        self.assertFalse(ok)
        self.assertIn("Invalid date", message)


class UpdateExpenseTests(DataFilesTestCase):
    def update(self, expense_id="1", **fields):
        return core.update_expense(self.expenses, self.history, expense_id, **fields)

    def test_invalid_date_changes_nothing(self):
        before = [e.copy() for e in self.expenses]
        ok, message = self.update(amount="99.99", category="Rent", date="not-a-date")
        self.assertFalse(ok)
        self.assertIn("Invalid date", message)
        self.assertEqual(self.expenses, before)
        self.assertEqual(self.history, [])
        self.assertEqual(self.read_file(self.data_file), SEED_CSV)
        self.assertFalse(os.path.exists(self.history_file))

    def test_invalid_amount_changes_nothing(self):
        before = [e.copy() for e in self.expenses]
        for bad in ["nan", "0.001", "-1", ""]:
            ok, _ = self.update(amount=bad, category="Rent", description="new")
            self.assertFalse(ok, bad)
        self.assertEqual(self.expenses, before)
        self.assertEqual(self.history, [])

    def test_unknown_expense_id(self):
        ok, message = self.update(expense_id="99", amount="5")
        self.assertFalse(ok)
        self.assertIn("not found", message)

    def test_successful_edit_updates_data(self):
        ok, _ = self.update(amount="99.99", category="rent")
        self.assertTrue(ok)
        reloaded = core.load_expenses()
        self.assertEqual(reloaded[0]["amount"], Decimal("99.99"))
        self.assertEqual(reloaded[0]["category"], "Rent")
        self.assertEqual(reloaded[0]["description"], "Trip")  # not submitted: untouched

    def test_empty_description_clears_it(self):
        ok, _ = self.update(description="   ")
        self.assertTrue(ok)
        self.assertEqual(core.load_expenses()[0]["description"], "")

    def test_empty_category_becomes_other(self):
        self.update(category="")
        self.assertEqual(self.expenses[0]["category"], "Other")

    def test_resubmitting_same_values_is_not_an_edit(self):
        # 500.0 (legacy formatting) equals 500.00, so this changes nothing
        ok, message = self.update(amount="500.00", category="food", description="Trip", date="2026-01-26")
        self.assertTrue(ok)
        self.assertEqual(message, "No changes to save.")
        self.assertEqual(self.history, [])
        self.assertFalse(os.path.exists(self.history_file))


class SaveFailureTests(DataFilesTestCase):
    def snapshot(self):
        return [e.copy() for e in self.expenses], [h.copy() for h in self.history]

    def assert_unchanged(self, expenses_before, history_before):
        self.assertEqual(self.expenses, expenses_before)
        self.assertEqual(self.history, history_before)
        self.assertEqual(core.load_expenses(), expenses_before)  # what is on disk
        self.assertEqual(core.load_history(), history_before)
        self.assertEqual(self.leftover_temp_files(), [])

    def test_failed_add_raises_and_rolls_back(self):
        before = self.snapshot()
        with self.fail_saves():
            with self.assertRaises(OSError):
                core.add_expense(self.expenses, "5", "Food", "x")
        self.assert_unchanged(*before)

    def test_failed_edit_raises_and_rolls_back(self):
        before = self.snapshot()
        with self.fail_saves():
            with self.assertRaises(OSError):
                core.update_expense(self.expenses, self.history, "1", amount="1.00", category="Rent")
        self.assert_unchanged(*before)
        self.assertEqual(self.read_file(self.data_file), SEED_CSV)  # never touched
        self.assertFalse(os.path.exists(self.history_file))

    def test_failed_delete_raises_and_rolls_back(self):
        before = self.snapshot()
        with self.fail_saves():
            with self.assertRaises(OSError):
                core.delete_expense(self.expenses, "1")
        self.assert_unchanged(*before)

    def test_failed_history_save_restores_expense_and_file(self):
        before = self.snapshot()
        real_save_history = core.save_history

        def boom(*args, **kwargs):
            raise OSError("history disk full")

        core.save_history = boom
        try:
            with self.assertRaises(OSError):
                core.update_expense(self.expenses, self.history, "1", amount="1.00")
        finally:
            core.save_history = real_save_history
        self.assert_unchanged(*before)


class HistoryTests(DataFilesTestCase):
    def test_records_only_changed_fields_with_before_and_after(self):
        core.update_expense(self.expenses, self.history, "1",
                            amount="600", category="Food", description="Trip", date="2026-02-01")
        self.assertEqual(len(self.history), 2)  # amount and date changed; category/description did not
        by_field = {h["field"]: h for h in self.history}
        self.assertEqual((by_field["amount"]["old_value"], by_field["amount"]["new_value"]), ("500.00", "600.00"))
        self.assertEqual((by_field["date"]["old_value"], by_field["date"]["new_value"]), ("2026-01-26", "2026-02-01"))
        for row in self.history:
            self.assertEqual(row["expense_id"], "1")
            self.assertRegex(row["timestamp"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

    def test_history_is_persisted_and_survives_reload(self):
        core.update_expense(self.expenses, self.history, "1", description="")
        core.update_expense(self.expenses, self.history, "2", amount="1.50")
        reloaded = core.load_history()
        self.assertEqual(reloaded, self.history)
        edits = core.edits_for(reloaded, "1")
        self.assertEqual(len(edits), 1)
        self.assertEqual(edits[0]["changes"], [{"field": "description", "old": "Trip", "new": ""}])
        self.assertEqual(core.edited_ids(reloaded), {"1", "2"})

    def test_edits_are_grouped_and_newest_first(self):
        core.update_expense(self.expenses, self.history, "1", amount="10")
        core.update_expense(self.expenses, self.history, "1", amount="20", category="Rent")
        edits = core.edits_for(self.history, "1")
        self.assertEqual([e["edit_id"] for e in edits], ["2", "1"])
        self.assertEqual(len(edits[0]["changes"]), 2)

    def test_add_and_delete_do_not_create_edits_and_history_survives_delete(self):
        core.add_expense(self.expenses, "5", "Food", "x")
        self.assertEqual(self.history, [])
        core.update_expense(self.expenses, self.history, "1", amount="10")
        core.delete_expense(self.expenses, "1")
        self.assertEqual(len(core.edits_for(core.load_history(), "1")), 1)


class ReportingTests(DataFilesTestCase):
    def test_totals_use_exact_decimal_arithmetic(self):
        expenses = [{"expense_id": str(i), "amount": Decimal("0.10"), "category": "Food",
                     "description": "", "date": "2026-01-01"} for i in range(3)]
        self.assertEqual(core.total_spent(expenses), Decimal("0.30"))
        self.assertEqual(core.category_totals(expenses), {"Food": Decimal("0.30")})
