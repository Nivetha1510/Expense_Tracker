# Expense Tracker (Flask)

A web-based expense tracker converted from a console Python script.
Expenses are stored in CSV, with dictionary-based reporting by
category and month.

## Features
- **Add** an expense (amount, category, description, date - defaults to today)
- **View** all expenses, sorted by date
- **Edit** / **Delete** an existing expense
- **Filter** by category, by month, or by a date range (via the dashboard)
- **Category-wise summary** and **monthly summary** with a grand total

## Tech Stack
- Python 3, Flask, Jinja2 templates
- Storage: `expenses.csv`

## Project Structure
```
expense_web/
├── app.py             # Flask routes (web layer)
├── expense_core.py    # Date handling, storage, CRUD, reporting (business logic)
├── templates/
│   ├── layout.html
│   ├── index.html      # dashboard + filters + add form
│   ├── edit.html
│   └── summary.html
└── static/
    └── style.css
```

## Setup
```bash
pip install flask
python app.py
```
Then open http://127.0.0.1:5000 in your browser.

## Data Format
`expenses.csv` columns: `expense_id, amount, category, description, date` (date format `YYYY-MM-DD`).
