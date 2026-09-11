import pandas as pd
import psycopg2
from psycopg2.extras import Json
from datetime import date, datetime
import math

EXCEL_PATH = r"C:\ai-platform\data\odoo\artikelen_promati.xlsx"

DB = {
    "host": "localhost",
    "port": 15432,
    "dbname": "promati",
    "user": "postgres",
    "password": "SterkWachtwoord123",
}


def clean_value(value):
    """Maak Excel/Pandas waarden geschikt voor PostgreSQL en JSON."""
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, float):
        if math.isnan(value):
            return None
        return value

    return value


def clean_row(row):
    return {key: clean_value(value) for key, value in row.to_dict().items()}


df = pd.read_excel(EXCEL_PATH)

print("Kolommen in Excel:")
print(df.columns.tolist())

conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Optioneel: tabel leegmaken bij opnieuw importeren
cur.execute("truncate table stg_odoo_articles restart identity;")

for _, row in df.iterrows():
    raw = clean_row(row)

    cur.execute("""
        insert into stg_odoo_articles (
            product_name,
            main_category,
            category,
            internal_ref,
            product_category,
            template_labels,
            qty_available,
            available_qty,
            expected_qty,
            message_info,
            outgoing,
            sale_price,
            cost_price,
            uom,
            raw_json
        )
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        raw.get("Naam"),
        raw.get("Main category"),
        raw.get("Category name"),
        raw.get("Interne referentie"),
        raw.get("Productcategorie"),
        raw.get("Productsjabloonlabels"),
        raw.get("Beschikbare voorraad"),
        raw.get("Beschikbare voorraad"),
        raw.get("Verwachte hoeveelheid"),
        raw.get("Bericht bij een verkooporderregel"),
        raw.get("Uitgaand"),
        raw.get("Verkoopprijs"),
        raw.get("Kostprijs"),
        raw.get("Maateenheid"),
        Json(raw)
    ))

conn.commit()
cur.close()
conn.close()

print(f"{len(df)} artikelen ingeladen.")