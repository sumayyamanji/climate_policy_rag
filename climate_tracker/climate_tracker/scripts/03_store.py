#!/usr/bin/env python3
"""
Import structured JSON text files (from Scrapy) into the PostgreSQL database.
"""
import os
import json
import logging
import psycopg2
from pathlib import Path
from psycopg2.extras import Json
from dotenv import load_dotenv

# Setup
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRUCTURED_DIR = PROJECT_ROOT / 'data' / 'full_text' / 'structured'

# DB Connection
def get_connection():
    try:
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "climate"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        return None

# Load and combine text
def load_combined_text(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict) or "sections" not in data:
            logger.warning(f"Unexpected JSON format or no 'sections' in {json_path}")
            return None

        all_text = ""
        for section, section_data in data["sections"].items():
            content = section_data.get("content", [])
            if isinstance(content, list):
                section_text = "\n".join(content)
                all_text += f"\n## {section}\n{section_text}\n"

        return all_text.strip() if all_text.strip() else None

    except Exception as e:
        logger.warning(f"Failed to parse {json_path}: {e}")
        return None

# Update DB
def store_text(doc_id, full_text, conn, country_name):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO countries (doc_id, country, text, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (doc_id)
                DO UPDATE SET text = EXCLUDED.text, country = EXCLUDED.country, created_at = NOW()
            """, (doc_id, country_name, full_text))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error storing DB entry for {doc_id}: {e}")
        conn.rollback()
        return False

def main():
    logger.info(f"Looking for structured JSON files in: {STRUCTURED_DIR}")
    conn = get_connection()
    if not conn:
        return

    updated, failed = 0, 0

    for json_path in STRUCTURED_DIR.glob("*.json"):
        doc_id = json_path.name

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            country_name = data.get("country_name") or json_path.stem.capitalize()
            if not country_name:
                logger.warning(f"⚠ No country_name in {json_path}")
                failed += 1
                continue
        except Exception as e:
            logger.error(f"❌ Failed to read JSON {json_path}: {e}")
            failed += 1
            continue

        full_text = load_combined_text(json_path)
        if full_text:
            success = store_text(doc_id, full_text, conn, country_name)
            if success:
                logger.info(f"✔ Stored {doc_id}")
                updated += 1
            else:
                logger.error(f"✖ Failed to store {doc_id}")
                failed += 1
        else:
            logger.warning(f"✖ No text found in {json_path}")
            failed += 1

    conn.close()
    logger.info(f"\n✅ Done. Updated {updated} documents. Failed {failed}.")

if __name__ == "__main__":
    main()