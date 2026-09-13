import os
import mysql.connector
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "root"),
        database=os.getenv("MYSQL_DATABASE", "idx_exchange"),
    )


def load_all_listings(chunksize=10000):
    conn = get_connection()

    query = """
        SELECT
            L_ListingID,
            L_Address,
            L_City,
            L_Keyword2 AS beds,
            LM_Dec_3 AS baths,
            L_SystemPrice AS price,
            L_Remarks AS remarks
        FROM rets_property
        WHERE L_Remarks IS NOT NULL
          AND LENGTH(L_Remarks) > 50;
    """

    return conn, pd.read_sql(query, conn, chunksize=chunksize)


def main():
    output_dir = "data/processed"
    output_file = os.path.join(output_dir, "listing_full.csv")

    os.makedirs(output_dir, exist_ok=True)

    print("Connecting to MySQL database 'idx_exchange' and loading all eligible listings...")

    conn, chunks = load_all_listings(chunksize=10000)
    total_rows = 0

    try:
        for chunk_number, df_chunk in enumerate(chunks, start=1):
            df_chunk.to_csv(
                output_file,
                mode="w" if chunk_number == 1 else "a",
                header=(chunk_number == 1),
                index=False,
            )

            total_rows += len(df_chunk)
            print(f"Processed chunk {chunk_number}: {len(df_chunk)} rows | total: {total_rows}")
    finally:
        conn.close()

    print(f"Saved {total_rows} rows to {output_file}")


if __name__ == "__main__":
    main()
