# Liquid Mapping to Mapping Table Documentation Generator

You are a FHIR R4 integration expert specializing in reverse-engineering and documenting data transformation logic. Given an existing Liquid mapping template and input JSON structure, generate comprehensive mapping table documentation that captures ALL transformation logic, business rules, and source-specific patterns.

## Inputs

**Implementation Guide (IG) with Version:** {ig_version}

**FHIR Resource Name:** {resource_name}

**Backend Source System:** {backend_source}

**Input JSON (Backend Source Data Structure):**

```json
{input_json}
```

**Existing Liquid Mapping Template:**

```liquid
{liquid_mapping}
```

{extra_context_section}

---

## Critical Analysis Instructions

### 1. Source Type Detection (FIRST STEP)
**BEFORE analyzing field mappings, identify the source data type:**

Examine the input JSON structure, field naming patterns, and liquid template logic to detect:

| Source Type | Characteristic Patterns | Key Indicators |
|-------------|------------------------|----------------|
| **HL7v2 Message** | MSH, PID, DG1, OBX segments; Field[n] notation; pipe delimiters | Field names like `MSH.9`, `PID.5`, segment arrays |
| **HL7v3/CDA Document** | XML-like structure; templateId; clinical document elements | XML namespaces, section codes, CDA-specific elements |
| **FHIR Resource** | `resourceType` field; FHIR element paths; reference formats | Existing FHIR structure, profiles, extensions |
| **Database Export** | Relational table structures; primary/foreign keys; table.column names | JOIN patterns, table_name.column_name notation |
| **REST API Response** | Nested JSON objects; camelCase naming; API-specific fields | Embedded objects, reference IDs, API conventions |
| **CSV/Flat File** | Flat structure; column headers; delimiter patterns | No nesting, column-based access |
| **EDI/X12** | Segment codes (ISA, GS, ST); element separators; loops | EDI segment names, qualifier codes |
| **Proprietary/Custom** | Vendor-specific naming; custom schemas; unique patterns | Non-standard structures, vendor identifiers |

**Document the detected source type prominently in the Overview section with supporting evidence.**

### 2. Contained Resources Analysis

**Analyze the liquid template to identify:**
- Does it create contained resources? (Look for `"contained": [...]` blocks)
- Which resource types are contained? (Patient, Practitioner, Organization, etc.)
- What is the containment strategy? (Messaging, document, standalone, hybrid)
- How are local IDs generated? (e.g., `#patient-{id}`, `#org-{code}`)
- Is there deduplication logic? (Arrays to track added resources)

**Determine containment rationale based on:**

| Source Type | Typical Containment Strategy | Indicators in Template |
|-------------|------------------------------|------------------------|
| **HL7v2/HL7v3** | Contained (self-contained messages) | Embedded patient/provider data; no server lookups |
| **EDI/X12** | Contained (transaction-based) | Complete entity data in segments |
| **Database** | External references (entities managed independently) | Reference IDs only; foreign keys |
| **FHIR-to-FHIR** | External references (existing resources) | Reference format: `ResourceType/id` |
| **REST API** | Hybrid (depends on embedded vs references) | Check for complete objects vs IDs |

**Document:**
- Containment decision and rationale
- Duplication prevention patterns (if loops present)
- Local ID generation logic
- Reference format (# prefix for contained, ResourceType/id for external)

### 3. Transformation Complexity Analysis

**Identify and categorize transformation patterns:**

**Simple Transformations:**
- Direct field mapping (source.field → fhir.field)
- Data type conversions (string → dateTime)
- Simple filters (upcase, downcase, slice)

**Complex Transformations:**
- Multi-step logic chains (assign → filter → conditional)
- Nested conditionals (if/elsif/else chains)
- Loop iterations with transformations
- Code/terminology mappings
- Concatenations and string building
- Date/time format conversions with timezones

**Business Rule Transformations:**
- Status determination logic
- Conditional field inclusion/exclusion
- Default value assignments
- Validation and constraint enforcement

### 4. Source-Specific Pattern Recognition

**For HL7v2 Sources (if detected):**
- Segment parsing patterns (MSH, PID, OBX, DG1, etc.)
- Field/component/subcomponent navigation (Field[1].Component[2])
- Repeating segment handling (loops over OBX[], DG1[])
- Null flavor detection (empty fields, ^^^, |""|)
- Escape sequence handling (\F\, \S\, \T\)
- Message type implications (ADT→Patient+Encounter, ORU→Observation)

**For Database Sources (if detected):**
- Table.column naming patterns
- JOIN logic (multiple tables combined)
- Primary/foreign key relationships
- NULL handling (COALESCE, ISNULL patterns)
- Aggregate functions (if present in source data)

**For REST API Sources (if detected):**
- Nested object navigation
- Array iteration patterns
- Null vs undefined handling
- Pagination indicators (if applicable)
- API-specific conventions (camelCase, snake_case)

**For CDA/C-CDA Sources (if detected):**
- XML namespace handling
- templateId mappings
- Section code patterns
- Narrative text extraction
- Author/participant role mappings

**For FHIR-to-FHIR (if detected):**
- Profile mappings (source IG → target IG)
- Extension handling
- Terminology translation
- Version compatibility patterns

---

## Your Task

Generate a comprehensive markdown documentation file that describes the mapping logic, field-level transformations, business rules, and any special considerations for this liquid mapping. The documentation should be clear, detailed, and suitable for use by both developers and business analysts.

Your markdown file should include the following sections:

### 1. Title and Context
- Resource name and source system
- Implementation Guide ({ig_version})
- **Source Type:** [Auto-detected: HL7v2 | HL7v3 | FHIR | CDA | Database | REST API | CSV | EDI | Custom]
- **Detection Evidence:** [List key indicators that led to source type identification]
- Purpose and scope of this mapping

### 2. Data Flow Overview
- **Input Source:** Describe the backend source data structure with source type context
- **Output Target:** FHIR {resource_name} resource in {ig_version} format
- **Transformation Complexity:** [Simple | Moderate | Complex] - based on logic depth
- **High-level Summary:** Overall transformation strategy and approach

### 3. Contained Resources Strategy (If Applicable)

**Containment Approach:** [Using Contained | Using External References | Hybrid | None]

**If contained resources are used:**

| Resource Type | Local ID Pattern | Source Fields | Duplication Prevention | Rationale |
|---------------|------------------|---------------|----------------------|-----------|
| [e.g., Patient] | [e.g., #patient-{id}] | [Source identifier fields] | [Array tracking logic] | [Why contained based on source type] |

**Reference Format Analysis:**
- Contained references use: `#localId` format
- External references use: `ResourceType/id` format
- Document any conditional reference logic

**Deduplication Logic (if loops present):**
```liquid
[Extract actual deduplication code from template]
```

### 4. Field Mapping Table

Create a comprehensive table with the following columns:

| FHIR Field Path | Source Field/Logic | Transformation | Data Type | Required | Cardinality | Conditional | Notes |
|-----------------|-------------------|----------------|-----------|----------|-------------|-------------|-------|

For each FHIR field mapped in the liquid template, provide:
- **FHIR Field Path**: JSONPath notation (e.g., `resourceType`, `identifier[0].system`, `code.coding[0].code`)
- **Source Field/Logic**: Source field name OR logic description (e.g., `source.diagnosisCode`, `hard-coded`, `conditional: if X then Y`, `loop over segments`)
- **Transformation**: Description of any transformation applied (filters, formatting, code mapping, concatenation, etc.)
- **Data Type**: Source type → FHIR type (e.g., `string → string`, `date → dateTime`, `segment array → CodeableConcept`)
- **Required**: Yes/No (based on FHIR {ig_version} requirements)
- **Cardinality**: FHIR notation (1..1, 0..1, 0..*, 1..*)
- **Conditional**: Any conditional logic affecting this field (if/unless statements)
- **Notes**: Any additional context, business rules, edge cases, or source-specific considerations

**Group by:**
1. **Core/Required Fields** (FHIR required elements)
2. **Optional Fields** (FHIR optional elements)
3. **Extension Fields** (custom extensions)
4. **Contained Resources** (if applicable)

### 5. Liquid Syntax Elements Used

Document all Liquid-specific elements in the template:

**Variable Assignments:**
| Variable Name | Source Expression | Purpose | Scope |
|---------------|------------------|---------|-------|
| [e.g., patientId] | [e.g., source.patient.id] | [e.g., Store patient identifier for reference] | [e.g., Global/Loop-local] |

**Filters Applied:**
| Filter Name | Input | Output | Purpose | Example |
|-------------|-------|--------|---------|---------|
| [e.g., date: "%Y-%m-%d"] | [e.g., source.birthDate] | [e.g., "1990-01-15"] | [e.g., Format date as FHIR date] | [e.g., {{ birthDate \| date: "%Y-%m-%d" }}] |

**Conditional Logic:**
| Condition Expression | Type | Affected Fields | True Behavior | False/Else Behavior |
|---------------------|------|-----------------|---------------|---------------------|
| [e.g., {% if source.gender %}] | [if] | [gender] | [Map source.gender] | [Omit field] |

**Loop Iterations:**
| Loop Variable | Collection | Purpose | Nested Loops | Notes |
|---------------|------------|---------|--------------|-------|
| [e.g., diagnosis] | [e.g., source.diagnoses] | [e.g., Create Condition resources] | [Yes/No] | [Deduplication applied] |

**Array Access Patterns:**
- First element: `[0]`, `.first`, `| first`
- Last element: `.last`, `| last`  
- Indexing: `[n]` notation
- Size limiting: `| limit: n`

### 6. Conditional Mapping Patterns

For each conditional transformation, document:

| Condition | Liquid Code | Fields Affected | TRUE Mapping | FALSE/Default Mapping | Example Scenario |
|-----------|-------------|-----------------|--------------|----------------------|------------------|

**Complex Conditional Chains:**
```liquid
[Extract nested if/elsif/else blocks from template]
```

### 7. Terminology and Code Mappings

For each code/value transformation:

| Source Code/Value | Target FHIR Code | Code System URI | Display Value | Mapping Logic | Conditional | Notes |
|-------------------|------------------|-----------------|---------------|---------------|-------------|-------|

**Code System References:**
- List all code systems used with URIs
- Document versioning (e.g., ICD-10-CM version)
- Note any terminology service dependencies

### 8. Null and Empty Value Handling

Document how missing or empty data is handled:

| Field | Null Check Logic | Default Value | Behavior if Missing | Required Field Handling |
|-------|------------------|---------------|---------------------|------------------------|

**Patterns Observed:**
- Explicit null checks: `{% if field %}`, `{% if field != nil %}`, `{% if field != "" %}`
- Default assignments: `{% assign var = field | default: "defaultValue" %}`
- Required field guarantees: Hard-coded values, computed defaults
- Optional field omissions: Fields skipped if source is empty

### 9. Source Data Structure Expectations

Based on the liquid template analysis, describe the expected source data structure:

**Required Source Fields:**
- [List fields that MUST be present for mapping to work]

**Optional Source Fields:**
- [List fields that are conditionally accessed]

**Data Type Expectations:**
| Source Field | Expected Type | Expected Format | Cardinality | Notes |
|--------------|---------------|-----------------|-------------|-------|

**Nested Structure:**
```json
[Provide expected JSON schema or structure based on liquid template]
```

### 10. Business Rules and Assumptions

List key business rules or assumptions embedded in the liquid template:

| Rule Category | Description | Affected Fields | Implementation Logic | Rationale |
|---------------|-------------|-----------------|---------------------|-----------|

**Common Categories:**
- **Status Values:** Hard-coded statuses (active, preliminary, final)
- **Version Handling:** Code system versions, profile versions
- **Provenance:** Audit trail, authorship information
- **Reference Resolution:** How references are constructed or resolved
- **Default Values:** Business-driven defaults for missing data
- **Data Quality:** Assumptions about source data quality/completeness

### 11. Source-Specific Patterns (Based on Detected Type)

**[Document patterns specific to the detected source type]**

**For HL7v2 Sources:**
- **Message Type:** [e.g., ADT^A01, ORU^R01] and implications
- **Segment Parsing:** How segments are accessed (e.g., `MSH.9`, `PID.5.1`)
- **Repeating Segments:** How arrays are handled (e.g., loop over OBX[], DG1[])
- **Component Navigation:** Field/component/subcomponent patterns
- **Null Flavor Handling:** How empty fields (^^^, |""|) are processed
- **Escape Sequences:** Handling of \F\, \S\, \T\, \E\, \R\
- **Timezone Handling:** Date/time conversions with timezones

**For Database Sources:**
- **Table Relationships:** JOIN logic or foreign key mappings
- **Primary Keys:** How entity identifiers are mapped
- **NULL Handling:** SQL NULL patterns (COALESCE, ISNULL)
- **Data Type Conversions:** SQL types → FHIR types
- **Multi-valued Columns:** Parsing comma-separated or delimited values

**For REST API Sources:**
- **Nested Objects:** How deep nesting is navigated
- **Array Iterations:** Patterns for iterating API response arrays
- **Null vs Undefined:** Distinction between missing and null fields
- **API Conventions:** camelCase, snake_case, PascalCase handling

**For CDA/C-CDA Sources:**
- **XML Navigation:** XPath-like patterns in liquid
- **TemplateId Mappings:** Document-level or section-level templates
- **Section Codes:** LOINC section codes mapped to FHIR
- **Narrative Extraction:** How text/narrative is handled
- **Author/Participant Mapping:** Role assignments

**For FHIR-to-FHIR Sources:**
- **Profile Mapping:** Source IG → Target IG transformations
- **Extension Handling:** How extensions are mapped/transformed
- **Terminology Translation:** Code system mappings (if different)
- **Version Compatibility:** R3→R4 or R4→R5 patterns

### 12. Example Transformation

Provide a concrete, complete example:

**Input (Backend Source Data):**
```json
[Complete sample input based on the input JSON provided - include all relevant fields]
```

**Liquid Processing (Key Steps):**
1. [Step 1: Variable assignments]
2. [Step 2: Conditionals evaluated]
3. [Step 3: Loops executed]
4. [Step 4: Transformations applied]

**Output (FHIR {resource_name} Resource):**
```json
[Expected complete FHIR output after transformation - valid FHIR R4 JSON]
```

### 13. Dependencies and Prerequisites

List any:
- **Required Source Fields:** Fields that must be present
- **External Reference Data:** Code systems, terminology services
- **Included Templates:** Liquid partials or includes
- **Environment Variables/Parameters:** Configuration dependencies
- **External Resources:** Referenced resources that must exist (if external references used)

### 14. Validation and Constraints

Document:
- **FHIR R4 Validation:** Elements that match R4 spec requirements
- **{ig_version} Profile Constraints:** IG-specific requirements met
- **Must-Support Elements:** Elements marked as must-support in profile
- **Invariants:** Custom validation rules enforced in mapping
- **Cardinality Compliance:** How cardinality constraints are ensured
- **Data Type Compliance:** Type conversions ensure FHIR type correctness

### 15. Transformation Complexity Assessment

**Complexity Rating:** [Simple | Moderate | Complex | Very Complex]

**Factors Contributing to Complexity:**
- Number of source fields mapped: [count]
- Number of conditional branches: [count]
- Loop nesting depth: [depth]
- Number of contained resources: [count]
- Custom transformations: [count]
- Business rules embedded: [count]

**Maintenance Considerations:**
- [List areas that may require updates when source changes]
- [List areas sensitive to IG version changes]

### 16. Error Handling and Edge Cases

Document how the liquid template handles:

| Edge Case | Detection Logic | Handling Strategy | Fallback Behavior | Impact |
|-----------|----------------|-------------------|-------------------|--------|
| [e.g., Missing required field] | [e.g., {% if field %}] | [e.g., Use default] | [e.g., Empty string] | [e.g., May fail validation] |

**Common Edge Cases:**
- Missing required fields
- Null/empty values in loops
- Invalid code values
- Date format variations
- Array size mismatches
- Circular references (if applicable)

### 17. Performance Considerations

**If applicable, document:**
- **Large Array Processing:** How large datasets are handled
- **Nested Loops:** Performance implications of nested iterations
- **Conditional Overhead:** Complex conditional chains
- **String Operations:** Heavy string concatenation or transformations

---

## Instructions for Comprehensive Analysis

1. **Start with Source Type Detection:** Carefully examine input JSON, field names, and liquid template patterns to identify source type
2. **Analyze Contained Resources:** Identify if template creates contained resources, extraction deduplication logic, and document containment strategy
3. **Extract ALL Liquid Elements:** Parse every assign, if, for, filter, and transformation in the template
4. **Map Every Field:** Document every FHIR field created by the liquid template with complete transformation logic
5. **Identify Business Rules:** Extract implicit and explicit business rules, assumptions, and defaults
6. **Document Source-Specific Patterns:** Provide context based on detected source type (HL7v2 segment parsing, database joins, API navigation, etc.)
7. **Provide Complete Examples:** Use actual values from input JSON to create realistic transformation examples
8. **Be Thorough and Precise:** This documentation will be used by developers to understand, maintain, and modify the mapping
9. **Use Proper Markdown Formatting:** Headers, tables, code blocks for readability

**Output Format:** Comprehensive markdown (.md) file with all sections above. Use proper markdown formatting with headers, tables, and code blocks.

---

## Quality Checklist

- [ ] Source type correctly detected and documented with evidence
- [ ] Containment strategy identified and documented (if applicable)
- [ ] ALL liquid variable assignments documented
- [ ] ALL conditional logic extracted and explained
- [ ] ALL loop iterations documented with purpose
- [ ] ALL filters and transformations listed
- [ ] Complete field mapping table with every FHIR field
- [ ] Terminology mappings documented with code systems
- [ ] Null/empty value handling patterns identified
- [ ] Business rules and assumptions explicitly stated
- [ ] Source-specific patterns documented based on detected type
- [ ] Complete example transformation provided with valid FHIR JSON
- [ ] Edge cases and error handling documented
- [ ] Dependencies and prerequisites listed
- [ ] FHIR R4 and IG compliance verified
- [ ] Complexity assessment provided
- [ ] Documentation is clear, organized, and comprehensive
