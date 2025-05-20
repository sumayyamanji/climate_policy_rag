# Define here the models for your scraped items
# See documentation in: https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class ClimateTrackerItem(scrapy.Item):
    # Country information
    country_slug = scrapy.Field()  # URL slug for the country
    country_name = scrapy.Field()  # Full name of the country
    
    # Section data
    section_title = scrapy.Field()  # Title of the section (Summary, Targets, etc.)
    section_content = scrapy.Field()  # Content as list of text paragraphs
    section_url = scrapy.Field()  # URL where the section was scraped from
    
    # Metadata
    timestamp = scrapy.Field()  # When the data was scraped
    version = scrapy.Field()  # Version information for tracking changes

class CountryTextItem(scrapy.Item):
    doc_id = scrapy.Field()         # Corresponds to CountryModel.doc_id (e.g., country_slug)
    country = scrapy.Field()        # Corresponds to CountryModel.country (e.g., country_name)
    language = scrapy.Field()       # Corresponds to CountryModel.language
    text = scrapy.Field()           # Corresponds to CountryModel.text (aggregated content)
    url = scrapy.Field()            # Corresponds to CountryModel.url (main country page or summary URL)
    # embedding will be handled by a separate script
    # created_at will be handled by the database model default