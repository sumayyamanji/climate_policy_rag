

import json
import os
from itemadapter import ItemAdapter

class ClimateTrackerPipeline:
    def __init__(self):
        self.data_dir = os.path.abspath("climate_tracker/data/json")
        os.makedirs(self.data_dir, exist_ok=True)
        self.countries = set()
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        country_slug = adapter.get('country_slug')
        
        # Save JSON version of the item
        json_file = os.path.join(self.data_dir, f"{country_slug}_{adapter.get('section_title').lower().replace(' ', '_')}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(dict(item), f, ensure_ascii=False, indent=2)
        
        # Keep track of processed countries
        self.countries.add(country_slug)
        
        return item
    
    def close_spider(self, spider):
        # Create an index of all countries
        index_file = os.path.join(self.data_dir, "country_index.json")
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.countries), f, indent=2)
        
        spider.logger.info(f"Processed {len(self.countries)} countries in total")