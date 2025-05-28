#!/usr/bin/env python3
"""
Management script for Climate Action Tracker project.
Supports scraping and embedding generation.
"""

import click
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine, text

from climate_tracker.climate_tracker.models import Base, get_db_session
from climate_tracker.climate_tracker.utils import (
    now_london_time, generate_word_embeddings, save_word2vec_model
)
from climate_tracker.climate_tracker.scripts.generate_embeddings import generate_embeddings as generate_embeddings_main
from climate_tracker.climate_tracker.scripts.information_retrieval import retrieve_and_format_answers
from climate_tracker.climate_tracker.scripts.policy_extraction import run_policy_extraction
from climate_tracker.climate_tracker.scripts.tsne_and_heatmap import generate_visualizations
from climate_tracker.climate_tracker.scripts.evaluate_extraction import evaluate as run_evaluation
from climate_tracker.climate_tracker.scripts.qa_boxes import generate_qa_markdown

load_dotenv()

@click.group()
def cli():
    """Management commands for the climate policy extractor."""
    pass

# Constants
STRUCTURED_DIR = os.getenv("STRUCTURED_JSON_DIR", "data/full_text/structured")
EMBEDDING_SCRIPT = "climate_tracker/scripts/generate_embeddings.py"
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

@cli.command(name="scrapy_crawl")
def extract(log_level="INFO"):
    """Step 1: Run the Climate Action Tracker spider"""
    print(f"Starting Climate Action Tracker data extraction with log level {log_level}...")
    current_dir = Path(os.getcwd())

    if not (current_dir / "scrapy.cfg").exists():
        print(f"Error: scrapy.cfg not found in {current_dir}")
        print("Make sure you're running this script from the directory that contains scrapy.cfg")
        return False

    cmd = ["scrapy", "crawl", "climate_action_tracker_fulltext", f"--loglevel={log_level}"]
    print(f"Running command: {' '.join(cmd)}")
    print("---------- SPIDER OUTPUT BEGIN ----------")

    try:
        result = subprocess.run(cmd)
        print("---------- SPIDER OUTPUT END ----------")
        if result.returncode != 0:
            print(f"Error: Spider exited with code {result.returncode}")
            return False
        print("Data extraction completed successfully.")
        return True
    except Exception as e:
        print(f"Failed to run spider: {e}")
        return False

@cli.command(name="init_db")
def init_db():
    """Step 2: Initialize the database with vector support."""
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        Base.metadata.create_all(engine)
        click.echo("✅ Database initialized.")
    except Exception as e:
        click.echo(f"❌ Error initializing database: {e}")
        raise

@cli.command(name="create_table")
def create_table():
    """Step 3: Create the `countries` table."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                doc_id TEXT PRIMARY KEY,
                country TEXT,
                language TEXT,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        click.echo("✅ Table `countries` created or already exists.")
    except Exception as e:
        click.echo(f"❌ Failed to create table: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

@cli.command(name="store")
def store():
    """Step 4: Store extracted text into the database."""
    from climate_tracker.climate_tracker.scripts.store import main
    try:
        main()
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command(name="generate_embeddings")
@click.option('--batch-size', default=5, help='Batch size for processing')
@click.option('--max-chars', default=30000, help='Maximum characters per section')
@click.option('--only-country', help='Optionally limit to one country_doc_id (e.g., "gabon")')
def generate_embeddings(batch_size, max_chars, only_country):
    """Step 5: Generate embeddings for document sections."""
    generate_embeddings_main(
        batch_size=batch_size,
        max_chars=max_chars,
        only_country=only_country
    )

@cli.command(name="information_retrieval")
def information_retrieval():
    """Step 6: Run information retrieval pipeline."""
    retrieve_and_format_answers()

@cli.command(name="policy_extraction")
def policy_extraction():
    """Step 7: Extract policy targets."""
    run_policy_extraction()

@cli.command(name="visualize")
def visualize():
    """Step 8: Generate TSNE and heatmap visualizations."""
    generate_visualizations()

@cli.command(name="evaluate")
def evaluate():
    """Step 9: Evaluate policy extraction results."""
    run_evaluation()

@cli.command(name="qa_boxes")
def qa_boxes():
    """Step 10: Generate QA boxes."""
    generate_qa_markdown("output/policy_targets_output.json", "output/qa_boxes.md")

@cli.command(name="recreate_db")
def recreate_db():
    """Recreate all database tables (destructive)."""
    engine = create_engine(DATABASE_URL)
    click.echo("Dropping all tables...")
    Base.metadata.drop_all(engine)
    click.echo("Recreating all tables...")
    Base.metadata.create_all(engine)
    click.echo("✅ Database recreated successfully!")

@cli.command(name="drop_db")
def drop_db():
    """Drop all tables from the database."""
    if click.confirm('Are you sure you want to drop all tables?'):
        engine = create_engine(DATABASE_URL)
        Base.metadata.drop_all(engine)
        click.echo("Tables dropped.")

@cli.command(name="list_tables")
def list_tables():
    """List all tables in the database."""
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        tables = Base.metadata.tables.keys()
        if not tables:
            click.echo("No tables found.")
            return
        click.echo("Tables in the database:")
        for table in tables:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            click.echo(f"- {table} ({count} rows)")

if __name__ == "__main__":
    cli()
