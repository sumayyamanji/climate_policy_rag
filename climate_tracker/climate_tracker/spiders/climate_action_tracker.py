import scrapy
import os
import json
from datetime import datetime
from urllib.parse import urljoin
# from climate_tracker.items import ClimateTrackerItem, CountryTextItem # Old
from climate_tracker.items import ClimateTrackerItem, CountrySectionItem # New

class ClimateActionTrackerSpider(scrapy.Spider):
    name = "climate_action_tracker_fulltext"
    allowed_domains = ["climateactiontracker.org"]
    start_urls = ["https://climateactiontracker.org/countries/"]
    version = "1.0"  # Version tracking for the scraper
    
    def __init__(self, *args, **kwargs):
        super(ClimateActionTrackerSpider, self).__init__(*args, **kwargs)
        # # Dictionary to store country data by country_slug # Old
        # self.countries_data = {} # Old
        
        # # Dictionary to store unstructured data by country_slug # Old
        # self.unstructured_data = {} # Old
        
        # # Create the directory structure if it doesn't exist # Old
        # self.md_dir = os.path.abspath("climate_tracker/data/full_text/MD") # Old
        # self.json_dir = os.path.abspath("climate_tracker/data/full_text/structured") # Old
        # self.unstructured_dir = os.path.abspath("climate_tracker/data/full_text/unstructured") # Old
        
        # # Create directories # Old
        # os.makedirs(self.md_dir, exist_ok=True) # Old
        # os.makedirs(self.json_dir, exist_ok=True) # Old
        # os.makedirs(self.unstructured_dir, exist_ok=True) # Old
        self.logger.info("Spider initialized. Will yield CountrySectionItem instances.")

    def parse(self, response):
        country_links = response.css("a::attr(href)").getall()
        country_urls = [
            response.urljoin(link) for link in country_links if "/countries/" in link and link.count("/") == 3
        ]
        for url in set(country_urls):
            yield scrapy.Request(url=url, callback=self.parse_country)
    
    def parse_country(self, response):
        country_slug = response.url.split("/countries/")[-1].strip("/")
        country_name = response.css("h1::text").get() or response.css("title::text").get().split(" | ")[0].strip()
        country_main_url = response.url # This is the main country page URL

        self.logger.info(f"Processing country: {country_name} ({country_slug}), main URL: {country_main_url}")

        # # Initialize country data in the dictionary # Old
        # self.countries_data[country_slug] = { # Old
        #     "country_name": country_name, # Old
        #     "sections": {} # Old
        # } # Old
        
        # # Initialize unstructured data in the dictionary # Old
        # self.unstructured_data[country_slug] = { # Old
        #     "country_slug": country_slug, # Old
        #     "country_name": country_name, # Old
        #     "content": [], # Old
        #     "urls": {}, # Old
        #     "timestamp": datetime.now().isoformat(), # Old
        #     "version": self.version # Old
        # } # Old
        
        # Extract the Summary section directly from this page
        summary_title = "Summary"
        summary_text_list = self.extract_section_text(response) # Returns a list of paragraphs/text blocks
        summary_content_str = "\n\n".join(summary_text_list) # Join into a single string

        # self.save_section_md(country_slug, "Summary", summary_content) # Old

        # # Save to country data structure (structured format) # Old
        # self.countries_data[country_slug]["sections"]["Summary"] = { # Old
        #     "content": summary_content, # Old
        #     "url": response.url # Old
        # } # Old
        
        # # Add to unstructured data # Old
        # self.add_to_unstructured(country_slug, "Summary", summary_content, response.url) # Old

        # Yield CountrySectionItem for the Summary
        summary_item = CountrySectionItem()
        summary_item['country_doc_id'] = country_slug
        summary_item['country_name'] = country_name
        summary_item['country_main_url'] = country_main_url
        summary_item['section_title'] = summary_title
        summary_item['section_url'] = response.url # Summary section is on the main country page
        summary_item['section_text_content'] = summary_content_str
        # summary_item['language'] will use default 'en' from item definition

        self.logger.info(f"Yielding Summary section for {country_name}")
        yield summary_item
        
        # # Export JSON for structured format # Old
        # self.export_json(country_slug) # Old
        
        # # Export unstructured format # Old
        # self.export_unstructured_json(country_slug) # Old
        
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
                        # Pass necessary country info to parse_section
                        "country_doc_id": country_slug, 
                        "country_name": country_name,
                        "country_main_url": country_main_url,
                        "section_title_meta": title # Renamed to avoid clash with section_title from item
                    }
                )
    
    def parse_section(self, response):
        country_doc_id = response.meta["country_doc_id"]
        country_name = response.meta["country_name"]
        country_main_url = response.meta["country_main_url"]
        section_title = response.meta["section_title_meta"]
        
        section_text_list = self.extract_section_text(response) # Returns a list of paragraphs/text blocks
        section_content_str = "\n\n".join(section_text_list) # Join into a single string
        
        # self.save_section_md(country_doc_id, section_title, section_text_list) # Old, and used list
        
        # # Save to country data structure (structured format) # Old - this logic is now replaced by yielding items
        # if country_doc_id not in self.countries_data: # Old
        #     self.countries_data[country_doc_id] = { # Old
        #         "country_name": country_name, # Old
        #         "sections": {} # Old
        #     } # Old
        
        # self.countries_data[country_doc_id]["sections"][section_title] = { # Old
        #     "content": section_text_list, # Old
        #     "url": response.url # Old
        # } # Old
        
        # # Add to unstructured data # Old
        # self.add_to_unstructured(country_doc_id, section_title, section_text_list, response.url) # Old

        # Yield CountrySectionItem for this section
        section_item = CountrySectionItem()
        section_item['country_doc_id'] = country_doc_id
        section_item['country_name'] = country_name
        section_item['country_main_url'] = country_main_url
        section_item['section_title'] = section_title
        section_item['section_url'] = response.url # This section's specific URL
        section_item['section_text_content'] = section_content_str
        # section_item['language'] will use default 'en' from item definition

        self.logger.info(f"Yielding section '{section_title}' for {country_name}")
        yield section_item
        
        # # Export JSON files after each section update # Old
        # self.export_json(country_doc_id) # Old
        # self.export_unstructured_json(country_doc_id) # Old
    
    def add_to_unstructured(self, country_slug, section_title, content, url): # Old - Will be removed or heavily modified
        """Add section data to the unstructured format""" # Old
        # if country_slug not in self.unstructured_data: # Old
        #     # This should not happen, but just in case # Old
        #     self.unstructured_data[country_slug] = { # Old
        #         "country_slug": country_slug, # Old
        #         "country_name": self.countries_data[country_slug]["country_name"], # Old
        #         "content": [], # Old
        #         "urls": {}, # Old
        #         "timestamp": datetime.now().isoformat(), # Old
        #         "version": self.version # Old
        #     } # Old
        
        # # Add section title as a header # Old
        # self.unstructured_data[country_slug]["content"].append(f"# {section_title}") # Old
        
        # # Add all content paragraphs # Old
        # self.unstructured_data[country_slug]["content"].extend(content) # Old
        
        # # Add a separator between sections # Old
        # self.unstructured_data[country_slug]["content"].append("\n---\n") # Old
        
        # # Store the URL for this section # Old
        # self.unstructured_data[country_slug]["urls"][section_title] = url # Old
        pass # Commenting out content for now

    def extract_section_text(self, response):
        elements = response.css('.content-section__content p, .content-section__content li, .content-section__content h3, .content-section__left-side h3')
        content = []
        for element in elements:
            tag = element.root.tag
            # Extract HTML content and explicitly replace <b> and <strong> tags with Markdown bold syntax
            raw_html = element.get()
            selector = scrapy.Selector(text=raw_html)
            # Replace bold tags with Markdown syntax
            for bold_tag in selector.css('b, strong'):
                bold_text = ''.join(bold_tag.css('::text').getall())
                bold_html = bold_tag.get()
                markdown_bold_text = f"**{bold_text}**"
                raw_html = raw_html.replace(bold_html, markdown_bold_text)
            # Convert cleaned HTML to plain text
            text_selector = scrapy.Selector(text=raw_html)
            text = ''.join(text_selector.css('::text').getall()).strip()
            if text:
                if tag == "h3":
                    if element.attrib.get("id"):
                        content.append(f"\n## {text}\n")
                    else:
                        content.append(f"\n### {text}\n")
                elif tag == "li":
                    content.append(f"- {text}")
                else:
                    content.append(f"{text}\n")
        return content
    
    def save_section_md(self, country_slug, section_title, content): # Old - To be removed
        """Save section to a Markdown file""" # Old
        # # Use the MD directory path defined in __init__ # Old
        # file_path = os.path.join(self.md_dir, f"{country_slug}.md") # Old
        
        # with open(file_path, "a", encoding="utf-8") as f: # Old
        #     f.write(f"\n# {section_title}\n\n") # Old
        #     for paragraph in content: # Old
        #         f.write(f"{paragraph}\n") # Old
        # self.logger.info(f"Saved {section_title} for {country_slug} to Markdown") # Old
        pass # Commenting out content
    
    def export_json(self, country_slug): # Old - To be removed
        """Export data for a single country to a JSON file (structured format)""" # Old
        # if country_slug not in self.countries_data: # Old
        #     self.logger.warning(f"No data found for country {country_slug}") # Old
        #     return # Old
        
        # # Use the structured JSON directory path defined in __init__ # Old
        # file_path = os.path.join(self.json_dir, f"{country_slug}.json") # Old
        
        # with open(file_path, "w", encoding="utf-8") as f: # Old
        #     json.dump(self.countries_data[country_slug], f, ensure_ascii=False, indent=2) # Old
        # self.logger.info(f"Exported structured JSON data for {country_slug}") # Old
        pass # Commenting out content
    
    def export_unstructured_json(self, country_slug): # Old - To be removed
        """Export unstructured data for a country to a JSON file""" # Old
        # if country_slug not in self.unstructured_data: # Old
        #     self.logger.warning(f"No unstructured data found for country {country_slug}") # Old
        #     return # Old
        
        # # Use the unstructured directory path defined in __init__ # Old
        # file_path = os.path.join(self.unstructured_dir, f"{country_slug}.json") # Old
        
        # with open(file_path, "w", encoding="utf-8") as f: # Old
        #     json.dump(self.unstructured_data[country_slug], f, ensure_ascii=False, indent=2) # Old
        # self.logger.info(f"Exported unstructured JSON data for {country_slug}") # Old
        pass # Commenting out content
    
    def closed(self, reason):
        self.logger.info(f"Spider closed: {reason}")
        # self.logger.info(f"Total countries in unstructured_data for final processing: {len(self.unstructured_data)}") # Old

        # for country_slug, unstructured_entry in self.unstructured_data.items(): # Old - Iterate over self.unstructured_data
        #     # 'content' in unstructured_data is a list of text blocks/paragraphs
        #     full_text_content = "\n\n".join(unstructured_entry.get('content', []))

        #     if not full_text_content: # Skip if no text content was aggregated
        #         self.logger.warning(f"No text content in unstructured_data for {country_slug}, skipping CountryTextItem.")
        #         continue

        #     country_item = CountryTextItem()
        #     country_item['doc_id'] = country_slug
        #     country_item['country'] = unstructured_entry.get('country_name', country_slug.replace('-', ' ').title())
        #     country_item['language'] = 'en' # Assuming English for now, as in original logic
        #     country_item['text'] = full_text_content
            
        #     # Try to get a main URL. The 'urls' dict in unstructured_data stores section_title: url
        #     section_urls = unstructured_entry.get('urls', {})
        #     main_url = section_urls.get('Summary') # Prioritize Summary URL
        #     if not main_url and section_urls:
        #         main_url = next(iter(section_urls.values()), None) # Fallback to the first URL found

        #     # If main_url is still None, construct it from the country_slug
        #     if not main_url and country_slug:
        #         main_url = f"https://climateactiontracker.org/countries/{country_slug}/"
            
        #     # As an absolute last resort, if country_slug was also somehow empty (highly unlikely)
        #     if not main_url:
        #         main_url = "https://climateactiontracker.org/countries/" # Generic countries page

        #     country_item['url'] = main_url

        #     self.logger.info(f"Yielding CountryTextItem for {country_slug} from unstructured_data") # Old
        #     yield country_item # Old

        # # Keep the original logic for exporting individual JSON files if still desired # Old
        # # (Though this might be redundant if the pipeline handles all DB storage) # Old
        # self.logger.info("Exporting all individual country JSON files as a final step (if any pending).") # Old
        # # Check if keys exist before trying to iterate, to prevent errors if these dicts are unexpectedly empty # Old
        # if hasattr(self, 'countries_data') and self.countries_data: # Old
        #     for country_slug_cs in list(self.countries_data.keys()): # Use list() for safe iteration if dict changes # Old
        #         self.export_json(country_slug_cs) # Old
        
        # if hasattr(self, 'unstructured_data') and self.unstructured_data: # Old
        #     for country_slug_ud in list(self.unstructured_data.keys()): # Use list() # Old
        #         self.export_unstructured_json(country_slug_ud) # Old

        self.logger.info("All scraping and item yielding completed. Pipeline will handle database operations.")
        # self.logger.info("All export processes in closed() method finished.") # Old