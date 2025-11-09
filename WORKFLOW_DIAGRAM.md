# SEC Filing Workflow Diagram

## Workflow Flow

```
┌─────────────────┐
│   FileEvent     │ (file_id)
│  (Start Event)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│   download_file         │
│  - Get file metadata    │
│  - Download from cloud  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   parse_document        │
│  - LlamaParse (Agentic) │
│  - Convert to markdown  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  classify_document      │
│  - LlamaClassify        │
│  - Detect: 10-K/10-Q/8-K│
└────────┬────────────────┘
         │
         ▼
    ┌────┴────┐
    │  Route  │
    └─┬───┬───┬
      │   │   │
  10-K│   │10Q│  8-K
      │   │   │
      ▼   ▼   ▼
    ┌───────────────────────────────┐
    │ extract_data_based_on_type    │
    │                               │
    │  IF 10-K:                     │
    │    Extract: total_revenue,    │
    │             net_income,       │
    │             total_assets,     │
    │             total_liabilities │
    │                               │
    │  IF 10-Q:                     │
    │    Extract: quarterly_revenue,│
    │             quarterly_net_income,│
    │             total_assets,     │
    │             total_liabilities │
    │                               │
    │  IF 8-K:                      │
    │    Extract: events[] with     │
    │             category &        │
    │             description       │
    └───────────┬───────────────────┘
                │
                ▼
    ┌─────────────────────────┐
    │ record_extracted_data   │
    │  - Save to Agent Data   │
    │  - Handle deduplication │
    └────────┬────────────────┘
             │
             ▼
    ┌─────────────────┐
    │   StopEvent     │ (item_id)
    └─────────────────┘
```

## Event Flow

```
FileEvent
  └─> DownloadFileEvent
        └─> FileDownloadedEvent
              └─> FileParsedEvent (contains markdown)
                    └─> FileClassifiedEvent (contains document_type & confidence)
                          └─> ExtractedEvent (contains MySchema with classification + data)
                                └─> StopEvent
```

## Data Schema Structure

```
MySchema (Final Output)
├── document_type: "10-K" | "10-Q" | "8-K"
├── form_10k_data: Optional[Form10KData]
│   ├── total_revenue
│   ├── net_income
│   ├── total_assets
│   └── total_liabilities
├── form_10q_data: Optional[Form10QData]
│   ├── quarterly_revenue
│   ├── quarterly_net_income
│   ├── total_assets
│   └── total_liabilities
└── form_8k_data: Optional[Form8KData]
    └── events: list[Event8K]
        ├── category
        └── description
```

## LlamaCloud Services Integration

```
┌──────────────────────────────────────────────┐
│           LlamaCloud Services                │
├──────────────────────────────────────────────┤
│                                              │
│  LlamaParse                                  │
│    └─> parse_document step                  │
│                                              │
│  LlamaClassify                               │
│    └─> classify_document step                │
│                                              │
│  LlamaExtract (3 agents)                     │
│    ├─> Agent for 10-K                        │
│    ├─> Agent for 10-Q                        │
│    └─> Agent for 8-K                         │
│         └─> extract_data_based_on_type step  │
│                                              │
│  Agent Data API                              │
│    └─> record_extracted_data step            │
│                                              │
└──────────────────────────────────────────────┘
```

## Conditional Logic

The workflow uses a conditional branching pattern:

1. **Parse**: Universal - all documents are parsed the same way
2. **Classify**: Universal - all documents are classified
3. **Extract**: Conditional - based on classification result
   - 10-K → Use 10-K extraction agent with Form10KData schema
   - 10-Q → Use 10-Q extraction agent with Form10QData schema
   - 8-K → Use 8-K extraction agent with Form8KData schema
4. **Record**: Universal - all extracted data is recorded

This ensures each document type gets the most appropriate extraction treatment while maintaining a unified interface.
