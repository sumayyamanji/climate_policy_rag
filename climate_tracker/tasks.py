#!/usr/bin/env python3
"""
Management script for Climate Action Tracker project.
Supports scraping and embedding generation.
"""
import os
import sys
import subprocess
from pathlib import Path
import click
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from climate_tracker.models import Base, get_db_session, NDCDocumentModel, DocChunk
from climate_tracker.utils import now_london_time
from climate_tracker.utils import generate_word_embeddings, save_word2vec_model
from climate_tracker.scripts.generate_embeddings import generate_embeddings as generate_embeddings_main

load_dotenv()

# Constants
STRUCTURED_DIR = os.getenv("STRUCTURED_JSON_DIR", "data/full_text/structured")
EMBEDDING_SCRIPT = "climate_tracker/scripts/generate_embeddings.py"
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")
#######################
# Spider Extract Code #
#######################
def extract(log_level="INFO"):
    """
    Run the Climate Action Tracker spider to extract text data.
    """
    print(f"Starting Climate Action Tracker data extraction with log level {log_level}...")
    current_dir = Path(os.getcwd())

    if not (current_dir / "scrapy.cfg").exists():
        print(f"Error: scrapy.cfg not found in {current_dir}")
        print("Make sure you're running this script from the directory that contains scrapy.cfg")
        return False

    print(f"Working directory: {current_dir}")

    cmd = ["scrapy", "crawl", "climate_action_tracker_fulltext", f"--loglevel={log_level}"]
    print(f"Running command: {' '.join(cmd)}")
    print("Spider is now running. This may take some time...")
    print("---------- SPIDER OUTPUT BEGIN ----------")

    try:
        result = subprocess.run(cmd)
        print("---------- SPIDER OUTPUT END ----------")
        if result.returncode != 0:
            print(f"Error: Spider exited with code {result.returncode}")
            return False
        print(f"\nData extraction completed successfully.")
        data_dir = current_dir / "climate_tracker" / "data" / "full_text"
        if data_dir.exists():
            print(f"Data has been saved to: {data_dir}")
        return True
    except Exception as e:
        print(f"Failed to run spider: {e}")
        return False

@click.group()
def cli():
    """Management commands for the climate policy extractor."""
    pass

def create_engine_and_extension():
    """Create the database engine and vector extension."""
    engine = create_engine(DATABASE_URL)
    click.echo("Creating vector extension...")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    return engine

@click.command()
def create_table():
    """
    Create the `countries` table in the PostgreSQL database.
    """
    load_dotenv()
    try:
        conn = psycopg2.connect(
            DATABASE_URL
        )
        cursor = conn.cursor()

        create_stmt = """
        CREATE TABLE IF NOT EXISTS countries (
            doc_id TEXT PRIMARY KEY,
            country TEXT,
            language TEXT,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        cursor.execute(create_stmt)
        conn.commit()
        click.echo("✅ Table `countries` created or already exists.")
    except Exception as e:
        click.echo(f"❌ Failed to create table: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

@cli.command()
def recreate_db():
    """Recreate the database from scratch (WARNING: destructive operation)."""
    engine = create_engine_and_extension()
    
    # Drop all tables
    click.echo("Dropping all tables...")
    Base.metadata.drop_all(engine)
    
    # Recreate all tables
    click.echo("Recreating all tables...")
    Base.metadata.create_all(engine)
    
    click.echo("Database recreated successfully!")

@cli.command()
def init_db():
    load_dotenv()
    """Initialize the database with vector support."""
    engine = create_engine_and_extension()
    
    try:
        # Create vector extension first
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            click.echo("Vector extension installed")
        
        # Create all tables
        Base.metadata.create_all(engine)
        click.echo("Database tables created")
        
    except Exception as e:
        click.echo(f"Error initializing database: {e}")
        raise

@cli.command()
def drop_db():
    """Drop all tables from the database (WARNING: destructive operation)."""
    if click.confirm('Are you sure you want to drop all tables? This cannot be undone!'):
        engine = create_engine(DATABASE_URL)
        
        # Drop all tables
        click.echo("Dropping all tables...")
        Base.metadata.drop_all(engine)
        
        click.echo("Database tables dropped successfully!")
    else:
        click.echo("Operation cancelled.")

@cli.command()
def list_tables():
    """List all tables in the database."""
    engine = create_engine(DATABASE_URL)
    
    # Get all table names
    with engine.connect() as conn:
        tables = Base.metadata.tables.keys()
        
        if not tables:
            click.echo("No tables found in the database.")
            return
        
        click.echo("\nTables in the database:")
        for table in tables:
            # Get row count
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            click.echo(f"- {table} ({count} rows)")

@cli.command()
def store_text(pdf_dir):
    """Store text from JSON files."""
    from climate_tracker.scripts.store_text import main
    try:
        main()
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command()
@click.option('--batch-size', default=10, help='Number of documents to process in each batch')
@click.option('--model-name', default='all-mpnet-base-v2', help='Name of the sentence-transformer model to use')
@click.option('--sentence-based/--character-based', default=True, help='Whether to chunk by sentences or character count')
@click.option('--chunk-size', default=500, help='Max size of each text chunk')
@click.option('--overlap', default=200, help='Overlap between chunks')
@click.option('--force/--no-force', default=False, help='Force reprocessing of documents')
def document_chunking(batch_size, model_name, sentence_based, chunk_size, overlap, force):
    """Generate embeddings for document chunks using sentence-transformers."""
    # Import the script and run it with subprocess
    import subprocess
    import sys
    
    click.echo("Generating document chunk embeddings...")
    
    # Construct the command to run the script directly
    cmd = [
        sys.executable,  # Python interpreter
        'climate_tracker/scripts/generate_embeddings.py',
        f'--batch-size={batch_size}',
        f'--model-name={model_name}',
        f'--chunk-size={chunk_size}',
        f'--overlap={overlap}'
    ]
    
    # Add boolean options
    if force:
        cmd.append('--force')
    else:
        cmd.append('--no-force')
        
    if sentence_based:
        cmd.append('--sentence-based')
    else:
        cmd.append('--character-based')
    
    # Run the script as a subprocess
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Print output
    if result.stdout:
        click.echo(result.stdout)
    if result.stderr:
        click.echo(result.stderr, err=True)
    
    # Check for errors
    if result.returncode != 0:
        raise click.ClickException("Document chunking failed")

if __name__ == "main":
    cli()