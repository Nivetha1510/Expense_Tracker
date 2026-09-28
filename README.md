# Expense Tracker (Flask)

A web-based expense tracker converted from a console Python script.
Expenses are stored in CSV, with dictionary-based reporting by
category and month, and a history of every edit.

## Features
- **Add** an expense (amount, category, description, date - defaults to today)
- **View** all expenses, sorted by date
- **Edit** / **Delete** an existing expense
- **Edit history** - see what changed on an expense, and when
- **Filter** by category, by month, or by a date range (via the dashboard)
- **Category-wise summary** and **monthly summary** with a grand total

## Tech Stack
- Python 3, Flask, Jinja2 templates
- Storage: `expenses.csv` and `edit_history.csv`

## Setup
```bash
pip install flask
python app.py
```
Then open http://127.0.0.1:5000 in your browser.

The data files are found relative to the project folder, so you can start
the app from any directory (for example `python path/to/app.py`).

### Secret key
Forms are protected against CSRF (forged requests from other websites)
using a token stored in your session, which is signed with a secret key.
For anything beyond local testing, set your own key:

```bash
# macOS / Linux
export SECRET_KEY="a-long-random-string"
# Windows PowerShell
$env:SECRET_KEY = "a-long-random-string"
```
If `SECRET_KEY` is not set, a random key is generated each time the app
starts. Everything still works, but open pages need a reload after a
restart (including the automatic restarts of debug mode).

### Running the tests
```bash
python -m unittest discover -s tests -t .
```
The tests use temporary copies of the data files and never touch your real
`expenses.csv` or `edit_history.csv`.

## Rules for amounts
Amounts are stored as exact decimal numbers, not floats. An amount must be
greater than zero and have at most two decimal places. `NaN`, infinity,
zero, negatives and values like `0.001` are rejected with a message
(they are never silently rounded).

## Editing and saving
- **Edits are all-or-nothing.** Every field is checked first. If any field
  is invalid (for example a bad date), nothing is changed and the form
  shows the error along with what you typed.
- **Clearing a description** is allowed: empty the box and save. An empty
  category becomes "Other".
- **Saving is safe.** The CSV is written to a temporary file and then
  swapped in, so a failed save can't leave a half-written file. If a save
  fails, the page says so, never says "added / updated / deleted", and the
  app's in-memory data goes back to how it was.
- **Unreadable data files stop the app from starting** (with an error
  message) instead of starting empty and overwriting your data.

## Edit history (beginner-friendly explanation)
Every time you successfully edit an expense, the app writes a note into
`edit_history.csv`, like an entry in a logbook. Each note says:

| Column       | Meaning                                              |
|--------------|------------------------------------------------------|
| `edit_id`    | Number of the edit (all fields changed in one save share it) |
| `expense_id` | Which expense was edited                             |
| `timestamp`  | When the edit was saved (local time of the server)   |
| `field`      | Which field changed: amount, category, description or date |
| `old_value`  | The value before the edit                            |
| `new_value`  | The value after the edit                             |

Example: changing expense 1's amount from 500 to 750 and its date adds two
rows with the same `edit_id`, one for `amount` and one for `date`.

**Where to see it:** on the dashboard, an edited expense shows
"(edited - view history)" next to its description. You can also open
"View edit history" from the edit page, or go straight to `/history/<id>`.

**Downloading it:** use the "Download edit history (CSV)" link on the
dashboard (or go to `/download/history`) to save the whole history, for all
expenses, as `edit_history.csv`. It opens in Excel or Google Sheets. If a
before/after value starts with `=`, `+`, `-` or `@`, the download adds a
leading `'` so a spreadsheet shows it as text instead of running it as a
formula (the copy on disk is left as is).

Things to know:
- Only fields that actually changed are recorded. Saving without changing
  anything, a rejected edit, or an edit that fails to save records nothing.
- Adding and deleting are not edits and are not in the history. If you
  delete an expense, its history is kept and can still be viewed.
- **There is no login, so the history records *when* something changed,
  not *who* changed it.**
- The history file is a plain CSV. Anyone with access to the files can
  change it, so treat it as a convenience log, not tamper-proof evidence.
- One entry, "(details not recorded)" for expense 1, was carried over from
  an earlier version that only stored the time of the last edit.

## Project Structure
```
expense_web/
├── app.py             # Flask routes (web layer)
├── expense_core.py    # Amounts, storage, CRUD, edit history, reporting
├── expenses.csv       # your expenses
├── edit_history.csv   # created on first edit
├── templates/
│   ├── layout.html
│   ├── index.html      # dashboard + filters + add form
│   ├── edit.html
│   ├── history.html    # edit history for one expense
│   └── summary.html
├── static/
│   └── style.css
└── tests/             # unit tests (unittest)
```

## Data Format
`expenses.csv` columns: `expense_id, amount, category, description, date`
(date format `YYYY-MM-DD`). Older files with amounts like `500.0` load fine.
