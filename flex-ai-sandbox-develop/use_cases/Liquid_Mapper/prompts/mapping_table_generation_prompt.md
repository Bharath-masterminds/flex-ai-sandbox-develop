# FHIR R4 Mapping Table Generation

You are a FHIR R4 integration expert. Generate a comprehensive mapping table for converting source data to FHIR R4 resources.

## Inputs

**Resource Name:** {resource_name}  
**Implementation Guide:** {ig_name}  
**Backend Source System:** {backend_source}
**Use Contained Resources:** {use_contained} (true/false - default: auto-detect based on source type)

**Source Input JSON:**
```json
{input_json}
```

**Additional Information:**
{additional_info}

**Reference Mapping Tables (Optional - for guidance):**
```
{reference_mappings}
```

**Source Liquid Mapping (Optional - if provided, use for structure guidance):**
```liquid
{liquid_mapping}
```

---

## Task

Generate a detailed mapping table in markdown format showing how to map the source JSON to the FHIR R4 {resource_name} resource following the {ig_name} implementation guide.

---

## Critical Instructions

1. **Source Type Detection:**
   - **FIRST:** Analyze the input JSON structure, field naming patterns, and backend source system
   - Identify if source is: HL7v2, HL7v3, FHIR, CDA, EDI/X12, Database, REST API, CSV, or other
   - Look for characteristic patterns:
     - HL7v2: MSH, PID, DG1, OBX segments with Field[n] notation
     - FHIR: "resourceType" field present
     - CDA: XML-like structure with clinical document elements
     - Database: Relational table structures with primary/foreign keys
     - REST API: JSON with nested objects or reference IDs
     - CSV: Flat structure with column headers
   - Document the detected source type in the Overview section

2. **Extensions Handling:** 
   - **If input is a liquid mapping:** IGNORE all extension elements completely. Do NOT document extensions in the mapping table.
   - **If input is JSON:** Document extensions only if they contain critical business data.
   - **If input is FHIR:** Map extensions appropriately based on source/target IG requirements.

3. **Use Reference Mappings:** Learn structure and patterns from provided reference mapping tables for the same resource but different sources/IGs.

4. **FHIR R4 Compliance:** Follow hl7.org/fhir/R4 specification strictly for element paths, data types, cardinality, and required elements.

4. **Contained Resources Decision:**
   
   **Auto-Detection Rules (when use_contained parameter not specified):**
   
   **Step 1: Identify Source Type**
   - Examine input structure, field naming conventions, and backend source system
   - Look for indicators: MSH/PID/DG1 segments (HL7v2), resourceType field (FHIR), REST API patterns, database schema, etc.
   
   **Step 2: Apply Containment Strategy Based on Source Type**
   
   | Source Type | Default Strategy | Rationale |
   |-------------|------------------|-----------|
   | **HL7v2/HL7v3 Messages** (MSH, PID, OBX, DG1, etc.) | **Contained** | Self-contained data packages; embedded resource data; no server dependency |
   | **EDI/X12 Messages** (837, 835, 270, etc.) | **Contained** | Transaction-based; complete context in message; one-time exchange |
   | **CDA/C-CDA Documents** | **Contained** | Document model requires self-contained resources |
   | **FHIR Resources** (existing resourceType) | **External** | Resources likely exist in FHIR server; use references |
   | **Database Exports** (relational tables) | **External** | Entities managed independently; use foreign keys as references |
   | **REST API Responses** | **Analyze** | Check for embedded objects vs reference IDs; decide accordingly |
   | **CSV/Flat Files** | **Analyze** | If includes complete related entity data → Contained; If only IDs → External |
   | **Custom/Proprietary Formats** | **Analyze** | Evaluate data completeness and use case |
   
   **Step 3: Apply Use Case Rules**
   
   **Use Contained Resources When:**
   - Processing messaging/transaction formats (HL7v2, HL7v3, EDI, etc.)
   - Creating document bundles for exchange or archival
   - Building standalone/self-contained FHIR resources
   - Source data includes **complete information** for referenced resources
   - Referenced resources are **context-specific** to the primary resource
   - **No guarantee** that referenced resources exist in target FHIR server
   - One-time data exchange or messaging scenarios
   - Migration/ETL scenarios where source system won't be queried again
   
   **Use External References When:**
   - Explicitly specified via `use_contained=false` parameter
   - Building persistent FHIR server resources with known reference IDs
   - Referenced resources exist independently and are managed separately
   - Source provides only reference IDs without complete data
   - Need to avoid data duplication across multiple resources
   - Working with existing FHIR server infrastructure
   - Referenced resource IDs are known, validated, and exist in target system
   - Building queryable resource relationships
   
   **Hybrid Approach (When Applicable):**
   - **Patient:** Contained for messaging; external for known patient IDs
   - **Practitioner:** Contained for message authors/observers; external for known provider registry
   - **Organization:** Contained for source facilities; external if organization registry exists
   - **Location:** Context-dependent; contained for specific encounter locations
   - **Device:** Contained for specific device instances; external for device definitions
   
   **Always Document:**
   - Source type detection (how you identified the source format)
   - Rationale for containment decision based on source type and use case
   - Duplication prevention strategy with unique identifiers
   - How to generate stable local IDs (e.g., `#patient-{source_id}`, `#org-{facility_code}`)

---

## Required Output Sections

### 1. Overview
- Resource: {resource_name}
- Source: {backend_source}
- **Source Type:** [Auto-detected type: HL7v2 | FHIR | CDA | Database | REST API | CSV | EDI | Other]
- IG: {ig_name}
- FHIR Version: R4
- **Containment Strategy:** [Using Contained | Using External References | Hybrid] - Based on source type detection

### 2. Core Field Mapping Table

| FHIR Element Path | Source Field/Path | Source Type | FHIR Type | Cardinality | Required | Transformation | Example | Notes |
|-------------------|-------------------|-------------|-----------|-------------|----------|----------------|---------|-------|

**Guidelines:**
- Map ALL fields from source JSON
- Use exact FHIR element paths (e.g., `Patient.identifier[0].system`)
- Document transformation logic (concatenation, filters, conditionals)
- Include example values from input JSON
- Mark required fields per FHIR R4 spec

### 3. Contained Resources (If Applicable)

**Containment Decision:** [State: Using Contained | Using External References | Hybrid Approach]  
**Rationale:** [Explain why based on source type, use case, and data availability]

**For each contained resource:**

| Resource Type | Local ID Pattern | Unique Source Field | Required Elements | Why Contained | Duplication Prevention |
|---------------|------------------|---------------------|-------------------|---------------|----------------------|

**Example:** 
```
| Patient | #patient-{unique_patient_id} | {source_patient_identifier} | identifier, name, gender, birthDate | {Reason based on source type - e.g., "HL7v2 ADT message with complete patient demographics" or "REST API response with embedded patient object"} | Use patient ID as stable identifier; check if already added in loop |
```

**Contained Resource Mapping Guidelines:**

1. **For Different Source Types:**
   
   **HL7v2 Messages (if detected):**
   - **Patient:** Map from PID segment → `#patient-{patient_id}`
   - **Practitioner:** Map from ROL/PV1 segments → `#practitioner-{provider_id}`
   - **Organization:** Map from PV1/MSH segments → `#org-{facility_id}`
   - **Encounter:** Map from PV1 segment → `#encounter-{visit_number}`
   
   **Database/Relational Sources (if detected):**
   - **Patient:** Map from patient table → `#patient-{primary_key}`
   - **Practitioner:** Map from provider/doctor table → `#practitioner-{provider_id}`
   - **Organization:** Map from facility/organization table → `#org-{org_id}`
   
   **REST API/JSON Sources (if detected):**
   - Identify embedded objects vs reference IDs
   - **Embedded objects with complete data** → Map to contained resources
   - **Reference IDs only** → Use external references
   
   **CDA/C-CDA Documents (if detected):**
   - **Patient:** Map from recordTarget → `#patient-{patient_id}`
   - **Author:** Map from author → `#practitioner-{author_id}`
   - **Custodian:** Map from custodian → `#org-{custodian_id}`
   
   **Generic/Unknown Sources:**
   - Analyze data structure to identify related entities
   - If complete entity data present → Map to contained resources
   - If only identifiers present → Use external references

2. **Local ID Generation Patterns:**
   - Use format: `#{resourceType}-{sourceSystemId}`
   - Examples: 
     - `#patient-12345` (from patient ID)
     - `#practitioner-DOC789` (from provider code)
     - `#org-HOSP001` (from facility code)
     - `#device-SN987654` (from device serial number)
   - Ensure IDs are **stable** across message/batch processing
   - Sanitize source IDs: remove spaces, special characters, convert to lowercase
   - Regex pattern: `^[a-z0-9\-\.]+$`

3. **Duplication Prevention in Loops:**
   ```liquid
   {% comment %} Generic deduplication pattern for any resource type {% endcomment %}
   {% assign addedResourceIds = "" | split: "" %}
   
   {% for item in sourceArray %}
     {% assign resourceId = item.uniqueIdentifier %}
     
     {% unless addedResourceIds contains resourceId %}
       {% comment %} Add contained resource {% endcomment %}
       {% assign addedResourceIds = addedResourceIds | push: resourceId %}
     {% endunless %}
     
     {% comment %} Reference the contained resource {% endcomment %}
   {% endfor %}
   ```

4. **Reference Format:**
   - **Contained:** `"reference": "#resource-type-id"` (with # prefix)
   - **External:** `"reference": "ResourceType/id"` (no # prefix)
   - **Conditional logic:**
     ```liquid
     {% if use_contained %}
       "reference": "#{{ resourceType | downcase }}-{{ sourceId }}"
     {% else %}
       "reference": "{{ resourceType }}/{{ sourceId }}"
     {% endif %}
     ```
   - Document the reference pattern in implementation guidance

### 4. Terminology Mappings

| FHIR Element | Source Value | Target Code | Code System URI | Display | Binding Strength |
|--------------|--------------|-------------|-----------------|---------|------------------|

### 5. Conditional Logic & Business Rules

Document:
- Condition expressions
- Affected fields
- True/false mappings
- Default values
- Null/empty handling rules

### 6. Data Type Transformations

| Source Type | FHIR Type | Transformation Logic | Filters Used | Example |
|-------------|-----------|---------------------|--------------|---------|

Examples: String date → dateTime, Object → CodeableConcept, Array → Reference[]

### 7. Validation Rules

- Required element checks
- Cardinality constraints
- Format validations
- Value range checks
- Terminology binding compliance

### 8. Example Transformation

**Input JSON:**
```json
[Show relevant excerpt from source]
```

**Output FHIR Resource:**
```json
[Show expected FHIR R4 resource output]
```

### 9. Implementation Guidance

**Liquid Template Considerations:**
- Variable assignments needed
- Filters to apply
- Loop iterations
- Conditional structures
- Reference format logic:
  - Contained resources: Use `#` prefix (e.g., `#patient-12345`)
  - External references: Use `ResourceType/id` format (e.g., `Patient/12345`)
  - Auto-detect based on containment strategy
- Error handling for missing data
- Deduplication logic for contained resources in loops

**Configuration:**
- Parameters needed:
  - `use_contained`: (true/false) - Override auto-detection
  - `default_contained_resources`: Array of resource types to contain (e.g., ["Patient", "Practitioner"])
  - `external_reference_resources`: Array of resource types to reference externally
  - `source_system_name`: Name/identifier of source system for audit
  - `target_fhir_server`: Target FHIR server endpoint (if using external references)
- External dependencies (code systems, terminology services)
- Code system versions
- Identifier systems (OIDs, URIs for source system identifiers)

**Source-Specific Guidance (if applicable):**

Provide guidance based on detected source type:

**For HL7v2 Sources:**
- Message type implications (ADT→Patient+Encounter, ORM→MedicationRequest, ORU→Observation, etc.)
- Segment parsing strategies (repeating segments, component/subcomponent navigation)
- Null flavor handling (empty fields, ^^^ patterns, |""|)
- Timezone considerations for datetime fields
- Escape sequence handling (\F\, \S\, \T\, \E\, \R\)

**For Database/SQL Sources:**
- Table join relationships
- Primary/foreign key mappings to references
- NULL handling strategies
- Data type conversions (VARCHAR→string, INT→integer, DATETIME→dateTime)
- Multi-valued columns (comma-separated → arrays)

**For REST API/JSON Sources:**
- Nested object handling
- Array iteration strategies
- Null vs undefined vs empty string handling
- Pagination considerations (if applicable)
- Authentication/authorization tokens

**For CDA/C-CDA Sources:**
- XML namespace handling
- templateId mappings to FHIR profiles
- Narrative text extraction (if applicable)
- Section code mappings
- Author/participant role mappings

**For CSV/Flat File Sources:**
- Column name normalization
- Header row handling
- Delimiter and quote character handling
- Multi-value column parsing (e.g., "value1;value2;value3")
- Date format detection and conversion

**For FHIR-to-FHIR Transformations:**
- Profile mappings (source IG → target IG)
- Extension handling and mapping
- Terminology translation (if different code systems)
- Version compatibility (R3→R4, R4→R5)

**For Generic/Unknown Sources:**
- Data structure analysis
- Field naming pattern detection
- Data type inference
- Identifier extraction strategies

---

## Output Format

Generate a complete markdown document following the structure above. Use tables for mapping information and code blocks for examples.

---

## Quality Checklist

- [ ] All required FHIR R4 elements mapped or have defaults
- [ ] Cardinality constraints respected
- [ ] Data types match FHIR R4 spec
- [ ] Code systems use proper URIs
- [ ] Source type correctly identified and documented
- [ ] Contained resources strategy documented with clear rationale based on source type
- [ ] Contained resources include duplication prevention logic
- [ ] References use correct format (# for contained, ResourceType/id for external)
- [ ] Auto-detection logic applied correctly based on source type
- [ ] Extensions ignored if source is liquid mapping
- [ ] Transformation logic is clear and reproducible
- [ ] Example output is valid FHIR R4 JSON
- [ ] Edge cases documented (null values, missing fields, repeating elements)
- [ ] Source-specific considerations documented (HL7v2, database, API, CDA, CSV, etc.)
- [ ] Loop iteration deduplication strategy included (if needed)
- [ ] Terminology mappings documented with proper code systems
- [ ] Data type transformations clearly explained
