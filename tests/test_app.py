import re
from decimal import Decimal

import app as webapp
import expense_core as core
from tests.helpers import DataFilesTestCase, SEED_CSV


class RouteTestCase(DataFilesTestCase):
    def setUp(self):
        super().setUp()
        # The app keeps its data in module-level lists; point them at this test's data.
        webapp.expenses[:] = self.expenses
        webapp.history[:] = self.history
        self.addCleanup(webapp.expenses.clear)
        self.addCleanup(webapp.history.clear)
        webapp.app.config["TESTING"] = True
        self.client = webapp.app.test_client()
        self.token = self.get_token()

    def get_token(self):
        html = self.client.get("/").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([0-9a-f]+)"', html).group(1)

    def post(self, url, **data):
        data.setdefault("csrf_token", self.token)
        return self.client.post(url, data=data, follow_redirects=True)

    def text(self, response):
        return response.get_data(as_text=True)


class PageTests(RouteTestCase):
    def test_dashboard_and_summary_render(self):
        body = self.text(self.client.get("/"))
        self.assertIn("Trip", body)
        self.assertIn("1500.00", body)
        self.assertEqual(self.client.get("/summary").status_code, 200)

    def test_date_range_filter(self):
        body = self.text(self.client.get("/?start=2026-01-01&end=2026-02-01"))
        self.assertIn("Trip", body)
        self.assertNotIn("home", body)

    def test_end_before_start_shows_error(self):
        body = self.text(self.client.get("/?start=2026-03-01&end=2026-02-01"))
        self.assertIn("end date must not be before the start date", body)
        self.assertIn("Trip", body)  # falls back to the full list

    def test_invalid_dates_show_error(self):
        body = self.text(self.client.get("/?start=nope&end=2026-02-01"))
        self.assertIn("Both dates must be valid", body)


class CsrfTests(RouteTestCase):
    def test_posts_without_valid_token_are_rejected(self):
        fresh = webapp.app.test_client()
        for url, data in [("/add", {"amount": "5"}), ("/edit/1", {"amount": "5"}), ("/delete/1", {})]:
            self.assertEqual(fresh.post(url, data=data).status_code, 400, url)
            self.assertEqual(fresh.post(url, data={**data, "csrf_token": "bogus"}).status_code, 400, url)
        self.assertEqual(len(webapp.expenses), 2)
        self.assertEqual(self.read_file(self.data_file), SEED_CSV)

    def test_forms_contain_the_token(self):
        self.assertGreaterEqual(self.text(self.client.get("/")).count(self.token), 3)
        self.assertIn(self.token, self.text(self.client.get("/edit/1")))


class AddRouteTests(RouteTestCase):
    def test_add_valid(self):
        body = self.text(self.post("/add", amount="4.20", category="food", description="snack"))
        self.assertIn("Expense added", body)
        self.assertEqual(core.load_expenses()[-1]["amount"], Decimal("4.20"))

    def test_add_invalid_amounts(self):
        for bad, expected in [("nan", "valid number"), ("0.001", "2 decimal places"), ("-3", "greater than 0")]:
            body = self.text(self.post("/add", amount=bad))
            self.assertIn(expected, body)
            self.assertNotIn("Expense added", body)
        self.assertEqual(len(webapp.expenses), 2)

    def test_save_failure_is_reported_and_not_called_success(self):
        with self.fail_saves():
            body = self.text(self.post("/add", amount="9"))
        self.assertIn("Could not save", body)
        self.assertNotIn("Expense added", body)
        self.assertEqual(len(webapp.expenses), 2)


class EditRouteTests(RouteTestCase):
    EDIT = dict(amount="750", category="Food", description="Trip", date="2026-01-26")

    def test_edit_records_history_and_shows_it(self):
        body = self.text(self.post("/edit/1", **self.EDIT))
        self.assertIn("Expense updated successfully", body)
        self.assertIn("edited - view history", body)

        page = self.text(self.client.get("/history/1"))
        self.assertIn("500.00", page)
        self.assertIn("750.00", page)
        self.assertEqual(page.count("<tr>"), 2)  # header row + the single changed field

    def test_history_persists_across_reload(self):
        self.post("/edit/1", **self.EDIT)
        webapp.history[:] = core.load_history()
        self.assertIn("750.00", self.text(self.client.get("/history/1")))

    def test_invalid_edit_leaves_expense_and_history_alone(self):
        body = self.text(self.post("/edit/1", amount="99", category="Rent", description="x", date="bad"))
        self.assertIn("Invalid date", body)
        self.assertNotIn("Expense updated", body)
        self.assertEqual(webapp.expenses[0]["amount"], Decimal("500.0"))
        self.assertEqual(webapp.expenses[0]["category"], "Food")
        self.assertEqual(webapp.history, [])
        self.assertEqual(self.read_file(self.data_file), SEED_CSV)
        self.assertIn('value="99"', body)  # what the user typed is kept in the form

    def test_can_clear_description(self):
        self.post("/edit/1", amount="500", category="Food", description="", date="2026-01-26")
        self.assertEqual(webapp.expenses[0]["description"], "")
        self.assertIn("description", self.text(self.client.get("/history/1")))

    def test_save_failure_reports_error_and_records_nothing(self):
        with self.fail_saves():
            body = self.text(self.post("/edit/1", **self.EDIT))
        self.assertIn("Could not save", body)
        self.assertNotIn("Expense updated", body)
        self.assertEqual(webapp.expenses[0]["amount"], Decimal("500.0"))
        self.assertEqual(webapp.history, [])
        self.assertIn("has not been edited", self.text(self.client.get("/history/1")))

    def test_unknown_expense(self):
        self.assertIn("not found", self.text(self.client.get("/edit/99", follow_redirects=True)))
        self.assertIn("not found", self.text(self.client.get("/history/99", follow_redirects=True)))


class DeleteRouteTests(RouteTestCase):
    def test_delete(self):
        self.assertIn("deleted", self.text(self.post("/delete/1")))
        self.assertEqual([e["expense_id"] for e in core.load_expenses()], ["2"])

    def test_save_failure_is_reported_and_expense_kept(self):
        with self.fail_saves():
            body = self.text(self.post("/delete/1"))
        self.assertIn("Could not save", body)
        self.assertNotIn("deleted", body)
        self.assertEqual(len(webapp.expenses), 2)

    def test_history_of_deleted_expense_is_still_viewable(self):
        self.post("/edit/1", amount="750", category="Food", description="Trip", date="2026-01-26")
        self.post("/delete/1")
        body = self.text(self.client.get("/history/1"))
        self.assertIn("has been deleted", body)
        self.assertIn("750.00", body)


class DownloadHistoryTests(RouteTestCase):
    def test_download_is_a_csv_attachment_with_all_edits(self):
        self.post("/edit/1", amount="750", category="Food", description="Trip", date="2026-01-26")
        self.post("/edit/2", amount="1.50", category="Utilities", description="home", date="2026-09-28")
        response = self.client.get("/download/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("edit_history.csv", response.headers["Content-Disposition"])
        lines = self.text(response).splitlines()
        self.assertEqual(lines[0], ",".join(core.HISTORY_FIELDS))
        self.assertEqual(len(lines), 3)
        self.assertIn("500.00,750.00", lines[1])

    def test_download_with_no_edits_is_just_the_header(self):
        self.assertEqual(self.text(self.client.get("/download/history")).splitlines(),
                         [",".join(core.HISTORY_FIELDS)])

    def test_download_link_is_on_the_dashboard(self):
        self.assertIn("/download/history", self.text(self.client.get("/")))

    def test_spreadsheet_formulas_are_defused(self):
        self.post("/edit/1", amount="500", category="Food", description="=SUM(A1)", date="2026-01-26")
        self.assertIn("'=SUM(A1)", self.text(self.client.get("/download/history")))
