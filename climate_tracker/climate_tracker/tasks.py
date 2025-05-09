"""
Simple utility script to run the Climate Tracker spider.
"""

import subprocess
import sys
from pathlib import Path
import os

def extract(log_level="INFO"):
    """
    Run the Climate Action Tracker spider to extract text data.
    
    Args:
        log_level (str): Logging level for scrapy (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    print(f"Starting Climate Action Tracker data extraction with log level {log_level}...")
    
    # Ensure the output directories exist
    project_root = Path(__file__).parent
    data_dir = project_root / "climate_tracker" / "data" / "full_text"
    md_dir = data_dir / "MD"
    structured_dir = data_dir / "structured"
    unstructured_dir = data_dir / "unstructured"
    
    for directory in [md_dir, structured_dir, unstructured_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    
    # Run the spider - using the exact name from your spider class
    cmd = ["scrapy", "crawl", "climate_action_tracker_fulltext", f"--loglevel={log_level}"]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Stream output in real-time
        for line in process.stdout:
            print(line, end='')
        
        # Wait for process to complete
        process.wait()
        
        if process.returncode != 0:
            stderr = process.stderr.read()
            print(f"Error running spider: {stderr}")
            return False
            
        print(f"\nData extraction completed successfully.")
        print(f"Data has been saved to:")
        print(f"  - Markdown files: {md_dir}")
        print(f"  - Structured JSON: {structured_dir}")
        print(f"  - Unstructured JSON: {unstructured_dir}")
        return True
        
    except Exception as e:
        print(f"Failed to run spider: {e}")
        return False

def main():
    """
    Main function that handles the command line interface.
    """
    if len(sys.argv) > 1 and sys.argv[1].lower() == "extract":
        # Get log level if provided
        log_level = "INFO"
        if len(sys.argv) > 2:
            log_level = sys.argv[2].upper()
        
        # Run the extraction
        extract(log_level)
    else:
        print("Usage: python tasks.py extract [log_level]")
        print("Example: python tasks.py extract DEBUG")

if __name__ == "__main__":
    main()