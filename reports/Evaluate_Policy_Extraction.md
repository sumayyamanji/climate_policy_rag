# Evaluating Policy Extraction

## Evaluation Methodology

Our climate policy analysis pipeline evaluated country-level policy targets across five key areas:

- `carbon_pricing`
- `efficiency_target`
- `electricity_net_zero`
- `net_zero_target`
- `sector_targets`

Ground truth annotations were manually created based on textual evidence from authoritative sources (e.g., Climate Action Tracker).
Only dates **relevant to actual policy commitments** were included. References or citations to other sources were deliberately excluded, even if detected by the model.

---

## Confidence Heatmap Overview (`output/confidence_heatmap.png`)

Running `climate_tracker/climate_tracker/scripts/tsne_and_heatmap.py`

The heatmap visualizes average model confidence scores across countries and policy areas. Key highlights:

- **High Confidence:** Countries like Germany, Vietnam, and the Philippines consistently show high extraction confidence (≥0.85) across all categories.
- **Low Confidence:** Ukraine scored below 0.70 across all five policy categories (see `low_confidence_summary.csv`), with the lowest per-country total confidence.

- Why did Ukraine score so low? 
    - Ukraine received low (< 0.70) confidence scores across all five policy areas — the lowest in the entire dataset.
    - This result aligns with the lack of structured information available in its Climate Action Tracker (CAT) page. The CAT entry for Ukraine explicitly states that its climate policy rating has been suspended due to the war; most recent assessment dates back to March 2022 with only a brief summary available. 
    - No detailed sector breakdowns, quantified targets, or updated long-term strategies are provided.
    - Led to weak embeddings, poor chunk relevance scores
    - Hence a data limitation, not model flaw
    
- Saudi Arabia and Switzerland had 0.80 confidence scores (on the lower side). Possible reasons: 
    -  Saudi Arabia often presents offset-based or intensity-based targets, which are hard to distinguish from absolute reduction commitments.
    - Switzerland uses market-based instruments like international carbon credits, which adds complexity in deciding whether a sectoral or electricity target has actually been set.

---

## t-SNE Analysis of Country Vectors (`output/tsne_plot.png`)

Running `climate_tracker/climate_tracker/scripts/tsne_and_heatmap.py`

t-SNE helps reveal how consistently the model trusted its answers across countries. Instead of only looking at F1 scores (which compare prediction vs truth), this view tells us:

- Where the model was confident but possibly wrong (overconfident extractions)
- Where it was underconfident but potentially correct
- Whether certain countries share similar policy documentation structure, which can inform future pretraining or prompt tuning

**Key Takeaways:**
- High-performing clusters are valuable case studies for consistent document structure (Philippines, Vietnam, Kenya, Thailand, Morocco). 
- Middle-of-pack countries suggest room for improvement in policy-specific parsing.
    - Upper Middle (EU, Peru, Colombia, Bhutan, Egypt, Ethiopia)
    - Bottom Left (UK, Costa Rica, Australia, USA, India): Countries here had more variation and lower overall confidence, especially on electricity targets and sector specificity. Some may use vague or policy-heavy language (e.g., Australia's 82% renewables confusion).
    - Center Cluster (Moderate Confidence) (Germany, Argentina, Mexico, Turkey, Kazakhstan):  middling performers, generally achieving solid extraction on one or two policy areas but showing uneven confidence elsewhere.
- Ukraine's isolation in the far right corner reinforces what we saw: it had low confidence in all 5 areas, correlating with missing or outdated documentation.


- The USA and Australia are far from EU/Vietnam despite being high-income — indicating that confidence did not correlate with economic development, but more with clarity and availability of climate documentation.

---

## Issues Identified in JSON Output

Using `argentina` as a case study:

### 1. Overgenerous "Yes" Labels on Vague Evidence 

- **Sector Targets:**
  ```json
  "yes_no": "yes",
  "quote": "...the government could set separate emission and reduction targets..."

Extracted sector = "LULUCF"

But the phrase is hypothetical. No actual sector-specific targets were committed.
➤ Should have been no
Model needs to decipher between could / may. 


### 2. False Negatives on Electricity Net Zero

The model outputs:
```json
"electricity_net_zero": {
  "yes_no": "no"
}
```

Even though:

* Clear net zero commitment appears on the top of the country's Net Zero section, and at the top of the Summary page
* Year tags like "2022", "2050" are correctly captured

The high number of "no" classifications for the electricity_net_zero target stemmed from a deliberately strict interpretation of what qualifies as a valid commitment. To be labeled "yes", the evidence needed to explicitly state a net zero electricity target, typically aligned with a 1.5°C-compatible timeline (e.g., 2035 for high-income countries). Partial measures — such as high renewable electricity shares (e.g., 82% renewables by 2030) or economy-wide net zero targets without electricity-specific milestones — were not considered sufficient. This strictness was intentional to avoid overestimating climate ambition based on vague or aspirational language. While this conservative approach helped reduce false positives, it may have led to lower recall and underestimated some genuine progress. With more time, I would explore a "planned" or "unclear" intermediate label to capture more nuance in ambiguous cases.

---

## Model Extraction Challenges:

- Sectoral target extraction struggled when sectors were:
    - Spread across multiple contexts
    - Mentioned ambiguously (e.g., "may include...", "the government could...")
- Electricity-specific targets were often missed even when clearly presented
- Citations and footnotes introduced irrelevant years, which misled the model during year extraction or quote selection


---

## Writing the `output/ground_truth_template.json` file 

Chose 9 countries to manually fill out the below fields: 

E.g. for Kenya: 

```json
},
  "kenya": {
    "net_zero_target": {
      "yes_no": "no",
      "target_year": null
    },
    "sector_targets": {
      "yes_no": "yes",
      "targets": [
        {
          "sector": ["transport", "agriculture"],
          "percentage_reduction": null,
          "target_year": "2037",
          "base_year": "2017"
        }
      ]
    },
    "efficiency_target": {
      "yes_no": "yes",
      "percentage_improvement": "2.8%",
      "target_year": null
    },
    "electricity_net_zero": {
      "yes_no": "no",
      "target_year": null
    },
    "carbon_pricing": {
      "yes_no": "no",
      "has_mechanism": false
    }
```

### Chose the following countries for the following reasons: 

#### 1. Argentina  
Argentina has submitted a long-term net zero strategy and includes LULUCF in its sector discussions. However, its targets have been rated as "Poor" by Climate Action Tracker, making it a useful case for analyzing vague or underdefined commitments in national strategies.

#### 2. Germany  
Germany has a legally binding 2045 net zero target and is considered one of the most transparent and advanced countries in terms of climate planning. It offers a strong reference point to evaluate system precision against a clearly articulated policy.

#### 3. India  
As a major developing economy with high emissions and differentiated responsibilities, India presents a critical test case to assess how well the model captures commitments with nuanced phrasing and conditional targets.

#### 4. Kenya  
Kenya's NDCs emphasize low-emission development pathways, but often lack detailed implementation plans. This makes it useful for testing the model's interpretation of aspirational versus firm targets.

#### 5. Australia  
Australia has committed to net zero by 2050, but its climate strategy has faced criticism for lacking enforceable sectoral targets and clarity. This makes it a relevant case to test how the system handles vague or partial commitments, especially when political commitment and legal enforceability diverge.

#### 6. USA  
As a global leader with a 2050 net zero pledge and sectoral plans like the Inflation Reduction Act, the USA offers a complex and multi-layered case to test the model's ability to extract multiple embedded targets.

#### 7. UAE  
As a fossil-fuel-rich country aiming for net zero, the UAE's documents often contain ambiguity and offset-based strategies. This challenges the system's ability to distinguish between absolute emissions reductions and offset reliance.

#### 8. Ethiopia  
Ethiopia expresses strong ambition to remain carbon neutral but lacks specifics on how this will be implemented. This tests the model's handling of vague targets with strong rhetorical language but low specificity.

#### 9. Brazil  
Brazil frequently references carbon neutrality and sectoral shifts, but its targets have been downgraded in ambition. Evaluating Brazil helps assess whether the model accurately flags rollbacks and inconsistencies in climate ambition.


----

## Evaluation Metrics Explained

We use **Precision**, **Recall**, and **F1-score** to assess model performance. We compared the ground truths from the 9 countries (`output/ground_truth_template.json`), with the outputs for the corresponding 9 countries (`output/policy_targets_outputs.json`). 

Running `climate_tracker/climate_tracker/scripts/evaluate_extraction.py`

Leading to the outputs: `output/country_f1_scores.png`, `output/evaluation_summary.md`, `output/label_f1_scores.png`


### Intro to the Metrics 

**Precision:** Of all the model's positive predictions, how many were correct? High precision ensures fewer false positives (e.g., avoids incorrectly saying a country has sector targets when it doesn't)
**Recall:** Of all the actual positives in the ground truth, how many did the model catch? High recall means the model doesn't miss true policy targets, even if they are phrased subtly.
**F1-Score:** Harmonic mean of precision and recall. Balances both metrics — essential for tasks like ours where both false positives and false negatives matter. 


### Overall Metrics

**Global Performance Summary:**

- **Precision:** `0.82`
- **Recall:** `0.70`
- **F1-score:** `0.80`

These values indicate a reasonably strong system, with a slight tendency to miss valid information (recall lagging behind precision).

---

### Per-Label Performance

| Target Field          | Precision | Recall | F1-score |
|:---------------------|:----------|:-------|:---------|
| `net_zero_target`    | 1.00      | 0.89   | 0.94     |
| `sector_targets`     | 1.00      | 0.80   | 0.89     |
| `efficiency_target`  | 0.88      | 1.00   | 0.93     |
| `electricity_net_zero`| 0.00     | 0.00   | 0.00     |
| `carbon_pricing`     | 0.40      | 1.00   | 0.57     |

🟨 **Key Insights:**
- `net_zero_target`, `efficiency_target`, and `sector_targets` show strong F1-scores (~0.90), indicating reliability in structured extraction.
- `electricity_net_zero` **completely failed**, with an F1 of `0.00`, revealing urgent issues in coverage logic or anchoring.
- `carbon_pricing` had decent recall but poor precision — it catches possible cases but overpredicts, often falsely attributing pricing policies.

---

### Per-Country Performance (9 Ground-Truth Countries)

| Country    | Precision | Recall | F1-score |
|:-----------|:----------|:-------|:---------|
| Argentina  | 0.50      | 0.50   | 0.50     |
| Australia  | 1.00      | 0.50   | 0.67     |
| Germany    | 1.00      | 0.60   | 0.75     |
| India      | 1.00      | 0.80   | 0.89     |
| Kenya      | 0.67      | 1.00   | 0.80     |
| USA        | 0.75      | 0.75   | 0.75     |
| UAE        | 1.00      | 0.60   | 0.75     |
| Ethiopia   | 0.75      | 0.75   | 0.75     |
| Brazil     | 1.00      | 0.67   | 0.80     |

**Country-level Takeaways:**
- **India and Kenya** had the highest F1-scores, suggesting the model handles both formal and conditional policy language well.
- **Argentina** had the **lowest F1-score** (0.50), with frequent false positives due to vague language ("could", "may") being misclassified as commitments.
- Most countries have **recall < 1**, indicating missed extractions. 
- **Australia and UAE** had perfect precision but lower recall, meaning the model played it safe — when it said "yes", it was correct, but it missed several valid cases.


### Low-Confidence Countries

The CSV `low_confidence_summary.csv` shows:

| Country  | Low Confidence Count (< 0.70) |
|----------|-------------------------------|
| Ukraine  | 5                             |

which proves our explanation above, relating to the lack of information on the Ukraine page on the CAT website. 


---

## Final Summary & Recommendations

The system performed well in identifying clearly articulated policy commitments, especially in areas like `net_zero_target`, `sector_targets`, and `efficiency_target`. The evaluation metrics showed high precision overall, suggesting that when the model predicted a positive answer, it was usually correct. However, lower recall across several categories — especially `electricity_net_zero` — revealed missed opportunities due to strict interpretation or extraction blind spots.

The t-SNE analysis showed how country-level confidence vectors clustered based on document clarity rather than economic status. Countries like the Philippines and Vietnam clustered tightly with high confidence across all five fields, while countries like Australia and the USA were more scattered, indicating extraction inconsistency. Ukraine was a clear outlier with universally low confidence, confirming the data limitation due to the suspended Climate Action Tracker rating.

A key finding was the tendency of the model to over-predict "yes" in cases of vague or hypothetical language (e.g., "the government could set sectoral targets"). This led to false positives in cases like Argentina, where the language was aspirational rather than concrete. Conversely, some clearly defined targets (e.g., net-zero electricity by 2035) were missed due to phrasing differences or section placement, leading to false negatives.


---

## Recommendations for Improvement

| Issue | Recommendation |
|:------|:---------------|
| Electricity net zero underperformance | Use document section titles (e.g., "Electricity Sector", "Power Decarbonization") to increase relevance and boost matching confidence |
| Overuse of "yes" on hypotheticals | Implement modal verb detection (`could`, `may`, `might`) in the extraction pipeline to down-rank speculative statements |
| Citation confusion | Apply regex filters to exclude citation-based year patterns (`IPCC`, `UNFCCC`, `[12]`, etc.) from year extraction logic |
| Low recall in cases like Argentina | Increase the context window size and integrate a keyword fallback system to capture more fragmented or scattered commitments |

---

## If I Had More Time...

If I had more time, I would enhance the classification logic to better differentiate between partial and full commitments. For example, many countries had high renewable electricity targets (e.g., 82% by 2030), but lacked a formal "net zero electricity" policy. These were correctly marked as "no" according to strict criteria, but ideally would be flagged as "partial" or "in progress." I would also extend the logic for handling modal language (e.g., "plans to", "could") and better surface relevant sections based on headings and semantic context. Finally, I would experiment with reinforcement learning from human feedback to better handle vague phrasing and conditional targets in developing countries.



