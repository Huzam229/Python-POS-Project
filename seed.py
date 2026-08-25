"""
Initialize the QuickPOS database schema without inserting demo records.

Run: python seed.py
For the old mock/demo records, run: python demo_seed.py
"""

from models import init_db


def main():
    print("Initializing database schema without demo data...")
    init_db()
    print("Database ready. No mock data was inserted and existing data was not changed.")


if __name__ == "__main__":
    main()