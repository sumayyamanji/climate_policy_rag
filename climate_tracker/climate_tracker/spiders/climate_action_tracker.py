import scrapy
import os
import json
from datetime import datetime
from urllib.parse import urljoin
from climate_tracker.items import ClimateTrackerItem
 
class ClimateActionTrackerSpider(scrapy.Spider):
    name = "climate_action_tracker_fulltext"
    allowed_domains = ["climateactiontracker.org"]
    start_urls = ["https://climateactiontracker.org/countries/"]
    version = "1.0"  # Version tracking for the scraper
   
    def __init__(self, *args, **kwargs):
        super(ClimateActionTrackerSpider, self).__init__(*args, **kwargs)
        # Dictionary to store country data by country_slug
        self.countries_data = {}
       
        # Dictionary to store unstructured data by country_slug
        self.unstructured_data = {}
       
        # Create the directory structure if it doesn't exist
        self.md_dir = os.path.abspath("climate_tracker/data/full_text/MD")
        self.json_dir = os.path.abspath("climate_tracker/data/full_text/structured")
        self.unstructured_dir = os.path.abspath("climate_tracker/data/full_text/unstructured")
       
        # Create directories
        os.makedirs(self.md_dir, exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)
        os.makedirs(self.unstructured_dir, exist_ok=True)
       
    def parse(self, response):
        country_links = response.css("a::attr(href)").getall()
        country_urls = [
            response.urljoin(link) for link in country_links if "/countries/" in link and link.count("/") == 3
        ]
        for url in set(country_urls):
            yield scrapy.Request(url=url, callback=self.parse_country)
   
    def parse_country(self, response):
        country_slug = response.url.split("/countries/")[-1].strip("/")
        # Try to extract country name from page title or heading
        country_name = response.css("h1::text").get() or response.css("title::text").get().split(" | ")[0].strip()
       
        # Initialize country data in the dictionary
        self.countries_data[country_slug] = {
            "country_name": country_name,
            "sections": {}
        }
       
        # Initialize unstructured data in the dictionary
        self.unstructured_data[country_slug] = {
            "country_slug": country_slug,
            "country_name": country_name,
            "content": [],
            "urls": {},
            "timestamp": datetime.now().isoformat(),
            "version": self.version
        }
       
        # Extract the Summary section directly from this page before proceeding
        summary_content = self.extract_section_text(response)
        self.save_section_md(country_slug, "Summary", summary_content)
       
        # Save to country data structure (structured format)
        self.countries_data[country_slug]["sections"]["Summary"] = {
            "content": summary_content,
            "url": response.url
        }
       
        # Add to unstructured data
        self.add_to_unstructured(country_slug, "Summary", summary_content, response.url)
       
        # Export JSON for structured format
        self.export_json(country_slug)
       
        # Export unstructured format
        self.export_unstructured_json(country_slug)
       
        # Extract links for other sections
        section_links = response.css('.nav.nav-pills a')
        sections = []
        for link in section_links:
            section_title = link.css("::text").get().strip()
            section_url = urljoin(response.url, link.attrib['href'])
            sections.append((section_title, section_url))
       
        section_order = ["Summary", "Targets", "Policies & Actions", "Net Zero Targets", "Assumptions", "Sources"]
        sorted_sections = sorted(sections, key=lambda x: section_order.index(x[0]) if x[0] in section_order else len(section_order))
       
        for title, url in sorted_sections:
            if title != "Summary":  # Skip Summary as we've already processed it
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_section,
                    meta={
                        "country": country_slug,
                        "country_name": country_name,
                        "section": title
                    }
                )
   
    def parse_section(self, response):
        country_slug = response.meta["country"]
        country_name = response.meta["country_name"]
        section_title = response.meta["section"]
        content = self.extract_section_text(response)
        self.save_section_md(country_slug, section_title, content)
       
        # Save to country data structure (structured format)
        if country_slug not in self.countries_data:
            self.countries_data[country_slug] = {
                "country_name": country_name,
                "sections": {}
            }
       
        self.countries_data[country_slug]["sections"][section_title] = {
            "content": content,
            "url": response.url
        }
       
        # Add to unstructured data
        self.add_to_unstructured(country_slug, section_title, content, response.url)
       
        # Export JSON files after each section update
        self.export_json(country_slug)
        self.export_unstructured_json(country_slug)
   
    def add_to_unstructured(self, country_slug, section_title, content, url):
        """Add section data to the unstructured format"""
        if country_slug not in self.unstructured_data:
            # This should not happen, but just in case
            self.unstructured_data[country_slug] = {
                "country_slug": country_slug,
                "country_name": self.countries_data[country_slug]["country_name"],
                "content": [],
                "urls": {},
                "timestamp": datetime.now().isoformat(),
                "version": self.version
            }
       
        # Add section title as a header
        self.unstructured_data[country_slug]["content"].append(f"## {section_title}")
        self.unstructured_data[country_slug]["content"].append(content)
        self.unstructured_data[country_slug]["urls"][section_title] = url
        self.unstructured_data[country_slug]["timestamp"] = datetime.now().isoformat()