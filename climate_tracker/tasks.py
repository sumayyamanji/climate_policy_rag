#!/usr/bin/env python3
"""
Management script for Climate Action Tracker project.
Supports scraping and embedding generation.
"""

import click
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine, text

from climate_tracker.models import Base, get_db_session
from climate_tracker.utils import now_london_time
from climate_tracker.utils import generate_word_embeddings, save_word2vec_model
from climate_tracker.scripts.generate_embeddings import generate_embeddings as generate_embeddings_main
from climate_tracker.scripts.information_retrieval import retrieve_and_format_answers
from climate_tracker.scripts.policy_extraction import run_policy_extraction
from climate_tracker.scripts.tsne_and_heatmap import generate_visualizations
from climate_tracker.scripts.evaluate_extraction import evaluate as run_evaluation
from climate_tracker.scripts.qa_boxes import generate_qa_markdown

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

def extract(log_level="INFO"):
    """Run the Climate Action Tracker spider to extract text data."""
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

def create_engine_and_extension():
    """Create the database engine and vector extension."""
    engine = create_engine(DATABASE_URL)
    click.echo("Creating vector extension...")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    return engine

@cli.command(name="01_init_db")
def init_db():
    """Initialize the database with vector support."""
    engine = create_engine_and_extension()
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        Base.metadata.create_all(engine)
        click.echo("Database initialized.")
    except Exception as e:
        click.echo(f"Error initializing database: {e}")
        raise

@cli.command(name="02_create_table")
def create_table():
    """Create the `countries` table."""
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

@cli.command(name="03_store")
def store():
    """Store extracted text into the database."""
    from climate_tracker.scripts.store_text import main
    try:
        main()
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command(name="04_generate_embeddings")
@click.option('--batch-size', default=10, help='Batch size for processing')
@click.option('--model-name', default='all-mpnet-base-v2', help='Transformer model name')
@click.option('--sentence-based/--character-based', default=True, help='Sentence vs character chunking')
@click.option('--chunk-size', default=500, help='Size of each chunk')
@click.option('--overlap', default=200, help='Chunk overlap')
@click.option('--force/--no-force', default=False, help='Force reprocessing')
def generate_embeddings(batch_size, model_name, sentence_based, chunk_size, overlap, force):
    """Generate embeddings for document chunks."""
    generate_embeddings_main(
        batch_size=batch_size,
        model_name=model_name,
        sentence_based=sentence_based,
        chunk_size=chunk_size,
        overlap=overlap,
        force=force
    )

@cli.command(name="05_information_retrieval")
def information_retrieval():
    """Run information retrieval pipeline."""
    retrieve_and_format_answers()

@cli.command(name="06_policy_extraction")
def policy_extraction():
    """Extract policy targets."""
    run_policy_extraction()

@cli.command(name="07_visualize")
def visualize():
    """Generate TSNE and heatmap visualizations."""
    generate_visualizations()

@cli.command(name="08_evaluate")
def evaluate():
    """Evaluate policy extraction results."""
    run_evaluation()

@cli.command(name="09_qa_boxes")
def qa_boxes():
    """Generate QA boxes."""
    generate_qa_markdown("output/policy_targets_output.json", "output/qa_boxes.md")

@cli.command()
def recreate_db():
    """Recreate all database tables (destructive)."""
    engine = create_engine_and_extension()
    click.echo("Dropping all tables...")
    Base.metadata.drop_all(engine)
    click.echo("Recreating all tables...")
    Base.metadata.create_all(engine)
    click.echo("Database recreated successfully!")

@cli.command()
def drop_db():
    """Drop all tables from the database."""
    if click.confirm('Are you sure you want to drop all tables?'):
        engine = create_engine(DATABASE_URL)
        Base.metadata.drop_all(engine)
        click.echo("Tables dropped.")

@cli.command()
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
