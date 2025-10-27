# SEC Filing Classification and Extraction Workflow

## Overview

This workflow processes SEC filings (10-K, 10-Q, 8-K) by:
1. **Classifying** the document type using LlamaClassify
2. **Extracting** structured data based on the document type using LlamaExtract
3. **Recording** the results with the classification information

## Workflow Steps

### 1. File Download (`download_file`)
- Downloads the file from cloud storage to a temporary location
- **Input**: `DownloadFileEvent` (file_id)
- **Output**: `FileDownloadedEvent` (file_id, file_path, filename)

### 2. Document Parsing (`parse_document`)
- Parses the PDF using LlamaParse (Agentic Mode with GPT-4-mini)
- Converts the document to markdown format
- **Input**: `FileDownloadedEvent`
- **Output**: `FileParsedEvent` (file_id, file_path, filename, markdown_content)

### 3. Document Classification (`classify_document`)
- Uses LlamaClassify to determine document type (10-K, 10-Q, or 8-K)
- Classification rules:
  - **10-K**: Annual report with audited financial statements
  - **10-Q**: Quarterly report with unaudited financial statements
  - **8-K**: Current report announcing major events
- **Input**: `FileParsedEvent`
- **Output**: `FileClassifiedEvent` (includes document_type and confidence)

### 4. Conditional Extraction (`extract_data_based_on_type`)
- Routes to the appropriate extraction schema based on classification:

  **If 10-K**: Extracts using `Form10KData` schema
  - `total_revenue`: Total revenue for fiscal year
  - `net_income`: Net income for fiscal year
  - `total_assets`: Total assets at fiscal year end
  - `total_liabilities`: Total liabilities at fiscal year end

  **If 10-Q**: Extracts using `Form10QData` schema
  - `quarterly_revenue`: Revenue for the quarter
  - `quarterly_net_income`: Net income for the quarter
  - `total_assets`: Total assets at quarter end
  - `total_liabilities`: Total liabilities at quarter end

  **If 8-K**: Extracts using `Form8KData` schema
  - `events`: List of events, each with:
    - `category`: Event category (e.g., Item 1.01, Item 2.02)
    - `description`: Description of the event

- **Input**: `FileClassifiedEvent`
- **Output**: `ExtractedEvent` (contains `MySchema` with classification + extracted data)

### 5. Record Data (`record_extracted_data`)
- Stores the extracted data in the agent data API
- Handles deduplication based on file hash
- **Input**: `ExtractedEvent`
- **Output**: `StopEvent` (with item_id)

## Final Output Schema

The final output is stored in `MySchema`, which contains:

```python
class MySchema(BaseModel):
    document_type: Optional[str]  # "10-K", "10-Q", or "8-K"
    form_10k_data: Optional[Form10KData]  # Populated only for 10-K
    form_10q_data: Optional[Form10QData]  # Populated only for 10-Q
    form_8k_data: Optional[Form8KData]    # Populated only for 8-K
```

This design ensures:
- The classification result is always stored
- Only the relevant extraction data is populated based on document type
- The schema is shared between Python and TypeScript for the frontend

## Key Design Decisions

1. **Decoupled Schemas**: The extraction schemas (Form10KData, Form10QData, Form8KData) are separate from the final output schema (MySchema). This allows LlamaExtract to work with specific schemas while the final output composes all possibilities.

2. **All Fields Optional**: All fields are marked as Optional to handle cases where LlamaExtract returns None for certain fields, preventing validation errors.

3. **Parse → Classify → Extract Pipeline**: The document is first parsed to markdown, then classified, and finally extracted. This allows classification to work on structured text and extraction to use the classification result.

4. **Multiple Extraction Agents**: Three separate extraction agents are created (one for each document type) with tailored system prompts and schemas, ensuring optimal extraction quality.

5. **ExtractedData.create()**: Uses `.create()` instead of `.from_extraction_result()` because the final MySchema is decoupled from the individual extraction results.

## LlamaCloud Services Used

- **LlamaParse**: PDF parsing with agentic mode (GPT-4-mini)
- **LlamaClassify**: Document type classification with natural language rules
- **LlamaExtract**: Structured data extraction with multiple agents (one per document type)
- **Agent Data API**: Storage and retrieval of extracted data

## Usage

The workflow is triggered when a file is uploaded to the system. It automatically:
1. Determines what type of SEC filing it is
2. Extracts the appropriate financial data
3. Stores the results for review in the UI

Users can review and correct the extracted data through the frontend interface.
