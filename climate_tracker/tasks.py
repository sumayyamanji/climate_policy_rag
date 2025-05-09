#!/usr/bin/env python3
"""
Simple utility script to run the Climate Tracker spider.
"""
import subprocess
import sys
import os
from pathlib import Path

def extract(log_level="INFO"):
    """
    Run the Climate Action Tracker spider to extract text data.
    """
    print(f"Starting Climate Action Tracker data extraction with log level {log_level}...")
    
    # Get the current directory (where this script is)
    current_dir = Path(os.getcwd())
    
    # Check if we're in the right directory (where scrapy.cfg is)
    if not (current_dir / "scrapy.cfg").exists():
        print(f"Error: scrapy.cfg not found in {current_dir}")
        print("Make sure you're running this script from the directory that contains scrapy.cfg")
        return False
    
    print(f"Working directory: {current_dir}")
    
    # Run the spider with direct output
    cmd = ["scrapy", "crawl", "climate_action_tracker_fulltext", f"--loglevel={log_level}"]
    print(f"Running command: {' '.join(cmd)}")
    print("Spider is now running. This may take some time...")
    print("---------- SPIDER OUTPUT BEGIN ----------")
    
    try:
        # Run the process without capturing output - this will send output directly to terminal
        result = subprocess.run(cmd)
        
        print("---------- SPIDER OUTPUT END ----------")
        
        if result.returncode != 0:
            print(f"Error: Spider exited with code {result.returncode}")
            return False
            
        print(f"\nData extraction completed successfully.")
        
        # Find the data directories
        data_dir = current_dir / "climate_tracker" / "data" / "full_text"
        if data_dir.exists():
            print(f"Data has been saved to: {data_dir}")
        
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