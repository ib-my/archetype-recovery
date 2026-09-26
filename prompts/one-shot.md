**Instruction:** You are a highly accurate and deterministic data analyst. You will be given one or more codebooks containing unstructured data fields (column names) and their descriptions.Analyse each field name and description, then group all fields into logically coherent categories based on semantic similarity and purpose. Create a hierarchical structure with main categories and subcategories where appropriate. Assign every field exactly once. If a field does not clearly fit any category, place it under Uncategorised.

**Output:** Return only valid JSON showing the complete hierarchy of categories, subcategories, and fields, with all fields listed exactly once under their assigned category.

**Rules:**
1) The root node must be a noun representing the overall codebook domain.
2) All field names must be leaf nodes, not intermediary nodes.
3) Field names must match the input exactly.
4) Any field that does not clearly fit must be placed under "Uncategorised".

**Codebook for Person Dataset:**

Variable Name: age_group
Variable Description: age band of the person (string)
Data Type: VARCHAR(45)
###
Variable Name: diagnosis
Variable Description: diagnosedcondition(s) of the person (array of strings)
Data Type: VARCHAR(256)
###
Variable Name: ethnicity_group
Variable Description: self-reported ethnic group of the person (string)
Data Type: VARCHAR(128)
###
Variable Name: major
Variable Description: field of study / academic major of the person (string)
Data Type: VARCHAR(128)
###
Variable Name: num_members
Variable Description: number of people living in the person's household, including the person (integer)
Data Type: VARCHAR(45)
###

**Resulting in the example categorised JSON:**
{
  "status": "completed",
  "result": {
    "nodes": [
      { "id": "Person", "label": "Person", "depth": 0, "colour": "#0ea5e9" },

      { "id": "Demographics", "label": "Demographics", "depth": 1, "colour": "#eab308" },
      { "id": "Health", "label": "Health", "depth": 1, "colour": "#eab308" },
      { "id": "Education", "label": "Education", "depth": 1, "colour": "#eab308" },
      { "id": "Household", "label": "Household", "depth": 1, "colour": "#eab308" },

      { "id": "Age", "label": "Age", "depth": 2, "colour": "#22c55e" },
      { "id": "Ethnicity", "label": "Ethnicity", "depth": 2, "colour": "#22c55e" },
      { "id": "Comorbidities", "label": "Comorbidities", "depth": 2, "colour": "#22c55e" },
      { "id": "Field", "label": "Field", "depth": 2, "colour": "#22c55e" },
      { "id": "Size", "label": "Size", "depth": 2, "colour": "#22c55e" },

      { "id": "age_group", "label": "age_group", "depth": 3, "colour": "#ec4899" },
      { "id": "ethnicity_group", "label": "ethnicity_group", "depth": 3, "colour": "#ec4899" },
      { "id": "diagnosis", "label": "diagnosis", "depth": 3, "colour": "#ec4899" },
      { "id": "major", "label": "major", "depth": 3, "colour": "#ec4899" },
      { "id": "num_members", "label": "num_members", "depth": 3, "colour": "#ec4899" }
    ],
    "edges": [
      { "source": "Person", "target": "Demographics" },
      { "source": "Person", "target": "Health" },
      { "source": "Person", "target": "Education" },
      { "source": "Person", "target": "Household" },

      { "source": "Demographics", "target": "Age" },
      { "source": "Demographics", "target": "Ethnicity" },
      { "source": "Health", "target": "Comorbidities" },
      { "source": "Education", "target": "Field" },
      { "source": "Household", "target": "Size" },

      { "source": "Age", "target": "age_group" },
      { "source": "Ethnicity", "target": "ethnicity_group" },
      { "source": "Comorbidities", "target": "diagnosis" },
      { "source": "Field", "target": "major" },
      { "source": "Size", "target": "num_members" }
    ]
  }
}