# FHIR R4 Liquid Template Generation

You are a FHIR R4 integration expert specializing in Liquid templating for healthcare data transformation.

Given the following inputs, generate a complete, production-ready, and standards-compliant Liquid mapping template for the specified FHIR resource.

---

## Inputs

**Implementation Guide (IG) Name:** {ig_name}  
**FHIR Resource Name:** {resource_name}  
**FHIR Release Version:** R4  
**Backend Source System:** {backend_source}

**Input JSON (Source Data Structure):**
```json
{input_json}
```

**Additional Information:**
{additional_info}

**Use Case / Business Scenario:**
{use_case}

**Date Format:** {date_format}

**Contained Resources Strategy:**
{use_contained}

**Note:** Use only standard FHIR R4 attributes. Do NOT generate or use FHIR extensions unless explicitly specified in the mapping table.

**Markdown Mapping Table (Primary Reference - for this specific source system):**
```markdown
{mapping_table}
```

**Reference Mapping Tables (Optional - for pattern guidance from other source systems):**
```markdown
{reference_mappings}
```

---

## Critical Generation Instructions

### 1. Source Type Detection & Adaptation

**Analyze the input JSON and mapping table to identify source type:**
- HL7v2 Message (segments: MSH, PID, OBX, DG1, etc.)
- Database Export (relational table structure)
- REST API Response (nested JSON objects)
- CDA/C-CDA Document (XML-like structure)
- CSV/Flat File (column-based structure)
- FHIR Resource (existing resourceType)
- EDI/X12 (segment codes and loops)

**Adapt Liquid template patterns based on source type:**

**For HL7v2 Sources:**
- Access segments as arrays: `{% for obx in source.OBX %}`
- Parse fields/components: `{{ PID.5[0].1 }}` (family name)
- Handle repeating segments with loops
- Implement null flavor checks: `{% if field != "" and field != "^^^" %}`
- Escape sequence handling if needed

**For Database Sources:**
- Access table.column notation: `{{ source.patient_table.first_name }}`
- Handle JOIN results (multiple related tables)
- NULL value checks: `{% if field != nil %}`
- Data type conversions (VARCHAR→string, INT→integer)

**For REST API Sources:**
- Navigate nested objects: `{{ source.patient.demographics.name }}`
- Iterate over arrays: `{% for item in source.items %}`
- Handle null vs undefined: `{% if field %}`

**For FHIR-to-FHIR:**
- Map profile elements: `{{ source.identifier[0].value }}`
- Transform extensions if needed
- Version compatibility patterns (R3→R4)

### 2. Contained Resources Implementation

**If use_contained is specified or mapping table indicates contained resources:**

**Implement complete contained resource blocks with:**

1. **Deduplication Logic (Critical for Loops):**
```liquid
{% comment %} Track added resource IDs to prevent duplicates {% endcomment %}
{% assign added_resource_ids = "" | split: "" %}

{% for item in source.array %}
  {% assign resource_id = item.unique_identifier %}
  
  {% unless added_resource_ids contains resource_id %}
    {% comment %} Add contained resource here {% endcomment %}
    {
      "resourceType": "ResourceType",
      "id": "{{ resource_id }}",
      ...
    }
    {% assign added_resource_ids = added_resource_ids | push: resource_id %}
  {% endunless %}
{% endfor %}
```

2. **Local ID Generation Pattern:**
- Use format: `resource-type-{source_id}` (lowercase, no # prefix in id field)
- Sanitize IDs: remove spaces, special characters
- Examples: `patient-12345`, `practitioner-doc789`, `org-hosp001`

3. **Reference Format:**
- Contained references: `"reference": "#resource-type-{id}"`
- External references: `"reference": "ResourceType/{id}"`
- Use # prefix in reference field, NOT in contained resource id field

4. **Required Elements for Contained Resources:**
- Include ALL required FHIR elements per R4 spec
- Patient: identifier, name, gender, birthDate (if available)
- Practitioner: identifier, name
- Organization: identifier, name
- Location: identifier, name, status
- Device: identifier, deviceName

### 3. Field Mapping from Mapping Table

**Follow the mapping table precisely:**
- Map ALL fields documented in the "Core Field Mapping Table" section
- Apply transformations exactly as specified
- Implement conditional logic as documented
- Use correct FHIR element paths
- Apply correct data types
- Respect cardinality constraints

**Transformation Patterns:**

**Date/DateTime Conversions:**
```liquid
{% comment %} Convert date string to FHIR date format {% endcomment %}
{{ source.date | date: "%Y-%m-%d" }}

{% comment %} Convert to FHIR dateTime with timezone {% endcomment %}
{{ source.datetime | date: "%Y-%m-%dT%H:%M:%S%:z" }}
```

**Terminology Mappings:**
```liquid
{% comment %} Map source code to FHIR CodeableConcept {% endcomment %}
{% if source.code == "A" %}
  {% assign code = "active" %}
  {% assign display = "Active" %}
{% elsif source.code == "I" %}
  {% assign code = "inactive" %}
  {% assign display = "Inactive" %}
{% else %}
  {% assign code = "unknown" %}
  {% assign display = "Unknown" %}
{% endif %}

"status": {
  "coding": [{
    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
    "code": "{{ code }}",
    "display": "{{ display }}"
  }],
  "text": "{{ display }}"
}
```

**Array Handling:**
```liquid
{% comment %} Iterate over source array to create FHIR array {% endcomment %}
"identifier": [
  {% for id in source.identifiers %}
    {
      "system": "{{ id.system }}",
      "value": "{{ id.value }}"
    }{% unless forloop.last %},{% endunless %}
  {% endfor %}
]
```

**Conditional Field Inclusion:**
```liquid
{% comment %} Only include field if source value exists {% endcomment %}
{% if source.field %}
  "fieldName": "{{ source.field }}",
{% endif %}
```

**String Concatenation:**
```liquid
{% comment %} Concatenate multiple source fields {% endcomment %}
{% assign full_name = source.first_name | append: " " | append: source.last_name %}
"text": "{{ full_name }}"
```

**Null/Empty Handling:**
```liquid
{% comment %} Provide default value if source is empty {% endcomment %}
"status": "{{ source.status | default: "unknown" }}"

{% comment %} Skip field entirely if source is empty {% endcomment %}
{% if source.field and source.field != "" %}
  "fieldName": "{{ source.field }}",
{% endif %}
```

### 4. FHIR R4 Compliance

**Ensure the generated template produces valid FHIR R4 JSON:**

- **resourceType**: Always first field, exact FHIR resource type name
- **id**: Local identifier for the resource
- **meta**: Include profile URL if specified in mapping table
- **Required Elements**: Include ALL required elements per R4 spec
- **Data Types**: Use correct FHIR data types (string, dateTime, boolean, integer, decimal, code, uri, etc.)
- **Cardinality**: Respect min/max cardinality (arrays for 0..*, single values for 0..1 or 1..1)
- **Code Systems**: Use proper URIs for code systems
- **References**: Correct format for contained vs external references
- **Extensions**: Only if explicitly documented in mapping table

**Required Elements by Resource (Common Examples):**

- **Patient**: identifier, name, gender
- **Condition**: subject, code, clinicalStatus (if available)
- **Observation**: status, code, subject
- **MedicationRequest**: status, intent, medicationCodeableConcept, subject
- **Encounter**: status, class, subject
- **DiagnosticReport**: status, code, subject

### 5. Code Quality Standards

**Generate production-ready Liquid templates with:**

1. **Comments:** Document complex logic, business rules, transformations
2. **Variable Names:** Use clear, descriptive names (patientId, diagnosisCode, etc.)
3. **Whitespace:** Proper indentation for readability
4. **Error Handling:** Check for nil, empty strings, missing fields
5. **Performance:** Minimize nested loops, avoid redundant operations
6. **Maintainability:** Modular structure, reusable variable assignments

**Example Structure:**
```liquid
{% comment %} ============================================
  FHIR R4 {resource_name} Liquid Template
  IG: {ig_name}
  Source: {backend_source}
  Generated: [Date]
============================================ {% endcomment %}

{% comment %} === Variable Assignments === {% endcomment %}
{% assign resource_id = source.id %}
{% assign status = source.status | default: "unknown" %}

{% comment %} === Main Resource === {% endcomment %}
{
  "resourceType": "{resource_name}",
  "id": "{{ resource_id }}",
  
  {% comment %} === Contained Resources === {% endcomment %}
  {% if use_contained %}
    "contained": [
      {% comment %} Patient, Practitioner, Organization, etc. {% endcomment %}
    ],
  {% endif %}
  
  {% comment %} === Core Fields === {% endcomment %}
  "identifier": [...],
  "status": "{{ status }}",
  ...
}
```

### 6. Validation & Quality Checks

**Before finalizing the template, verify:**

- [ ] All fields from mapping table are implemented
- [ ] Contained resources have deduplication logic (if loops used)
- [ ] References use correct format (# for contained)
- [ ] Required FHIR elements are present
- [ ] Data types match FHIR R4 spec
- [ ] Conditional logic matches mapping table
- [ ] Terminology mappings use correct code systems
- [ ] Date/time formats match specification
- [ ] Null/empty value handling is robust
- [ ] Comments explain complex transformations
- [ ] JSON structure is valid (commas, brackets)
- [ ] No FHIR extensions unless explicitly documented

---

## Output Requirements

**Generate ONLY the Liquid template in a code block, ready for production use.**

**Format:**
- Complete, valid Liquid template
- Produces valid FHIR R4 JSON when processed
- Includes ALL mappings from the mapping table
- Implements ALL business rules and transformations
- Handles edge cases (null, empty, missing data)
- Well-commented for maintainability

**Do NOT include:**
- Explanatory text outside the code block
- Partial or incomplete templates
- Placeholder comments like "add more fields here"
- Non-standard FHIR elements or extensions (unless documented)

**Output Format:**
```liquid
{% comment %} Your complete Liquid template here {% endcomment %}
{
  "resourceType": "{resource_name}",
  ...
}
```

---

## Quality Checklist

- [ ] Template produces valid FHIR R4 JSON
- [ ] All mapping table fields implemented
- [ ] Source type patterns correctly applied (HL7v2, DB, API, etc.)
- [ ] Contained resources have proper deduplication
- [ ] References use correct format (# prefix for contained)
- [ ] Required FHIR elements present
- [ ] Data types match R4 spec
- [ ] Cardinality constraints respected
- [ ] Code systems use proper URIs
- [ ] Date/time formats correct
- [ ] Null/empty handling robust
- [ ] Conditional logic matches mapping table
- [ ] Terminology mappings accurate
- [ ] Comments document complex logic
- [ ] No syntax errors (balanced brackets, commas)
- [ ] Production-ready quality
