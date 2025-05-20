"""
Centralized logging configuration for the climate policy extractor.
"""
import logging
# import colorlog # No longer needed for simplified version
# from scrapy.utils.project import get_project_settings # No longer needed for simplified version

# def setup_colored_logging(logger=None):
#     pass # Removed content

def get_logger(name):
    """
    Get a standard logger.
    """
    logger = logging.getLogger(name)
    # Basic configuration if no handlers are present for the root logger
    # Scrapy will likely configure its own handlers later.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    
    # Ensure a level is set if Scrapy hasn't set one from settings yet.
    # This is a basic default.
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
    return logger 