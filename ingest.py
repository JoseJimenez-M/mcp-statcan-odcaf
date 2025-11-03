import pandas as pd
from sqlalchemy import create_engine
import os

CSV_FILE = 'ODCAF_v1.0.csv'
DB_FILE = 'odcaf.db'
TABLE_NAME = 'facilities'


def ingest_data():
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found.")
        return

    try:
        df = pd.read_csv(CSV_FILE, encoding='utf-8')
    except UnicodeDecodeError:
        print("UTF-8 failed, trying latin1...")
        df = pd.read_csv(CSV_FILE, encoding='latin1')

    df.columns = df.columns.str.strip().str.lower().str.replace('[^a-z0-9_]', '', regex=True).str.replace(' ', '_')

    engine = create_engine(f'sqlite:///{DB_FILE}')

    df.to_sql(TABLE_NAME, engine, if_exists='replace', index=False, chunksize=1000)

    print(f"Data ingested into {DB_FILE} in table {TABLE_NAME}")
    print("Available columns after sanitizing:")
    print(df.columns.tolist())


if __name__ == "__main__":
    ingest_data()