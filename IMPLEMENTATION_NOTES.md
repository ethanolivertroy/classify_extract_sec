# Implementation Notes and Best Practices

## Key Implementation Details

### 1. Schema Design

#### Why Separate Extraction Schemas?
We created three separate schemas (`Form10KData`, `Form10QData`, `Form8KData`) instead of one unified schema because:
- Each document type has distinct fields (e.g., annual vs quarterly revenue)
- LlamaExtract performs better with focused, specific schemas
- Separation allows for tailored system prompts per document type

#### Why Compose in MySchema?
The final `MySchema` composes all three schemas because:
- Frontend needs a consistent interface
- TypeScript types can be auto-generated from a single schema
- The classification result needs to be stored alongside the data
- Only one sub-schema is populated at a time (based on document type)

#### Why All Fields are Optional?
All fields use `Optional[...]` because:
- LlamaExtract can sometimes return `None` for fields it can't find
- Making fields optional prevents validation errors
- Better to get partial data than fail completely
- The frontend can handle missing values gracefully

### 2. Workflow Step Design

#### Parse Before Classify
We parse first, then classify because:
- Classification works better on structured markdown than raw PDFs
- Parsing normalizes the document format
- Markdown is easier to process and faster for classification
- Parsed content can be reused for extraction

#### Classify Before Extract
We classify first, then extract because:
- Each document type needs a different extraction schema
- Classification determines which extraction agent to use
- Reduces extraction errors by using appropriate schemas
- Improves accuracy with document-specific system prompts

#### Using SourceText with Markdown
In the extraction step, we use:
```python
source_text = SourceText(
    text_content=event.markdown_content,
    filename=event.filename,
)
```
This is because:
- We already have parsed markdown from the previous step
- No need to re-parse the document
- Faster extraction since parsing is expensive
- LlamaExtract can work with text content directly

### 3. ExtractedData Creation

We use `ExtractedData.create()` instead of `.from_extraction_result()`:
```python
extracted_data = ExtractedData.create(
    data=final_data,
    file_id=event.file_id,
    file_name=event.filename,
    file_hash=file_hash,
)
```

**Why?**
- The final `MySchema` is decoupled from individual extraction results
- We manually construct `MySchema` by composing the extraction result
- `.from_extraction_result()` is for when extraction output = final output
- `.create()` is for when we need to compose or transform the extraction result

**Critical**: We ensure `file_id`, `file_name`, and `file_hash` are ALL set correctly.

### 4. Error Handling

Each step includes comprehensive error handling:
- Try-catch blocks around all operations
- Logging with `logger.error()` including stack traces
- UI notifications via `UIToast` events
- Exceptions are re-raised to trigger retry policies

### 5. LlamaCloud Configuration

#### LlamaParse Settings
- **Mode**: `parse_page_with_agent` (Agentic mode for best quality)
- **Model**: `openai-gpt-4-1-mini` (Good balance of speed and accuracy)
- **OCR**: Enabled with high-res mode for scanned documents
- **Tables**: Advanced table extraction with HTML output

#### LlamaExtract Settings
- **Mode**: `MULTIMODAL` (Best for financial documents with tables)
- **System Prompts**: Customized for each document type
- **Confidence Scores**: Enabled to track extraction quality
- **Reasoning**: Disabled (not needed for structured extraction)

#### LlamaClassify Rules
Classification rules are detailed and specific:
- Include document characteristics (audited vs unaudited)
- Mention typical field names (quarterly vs annual)
- Reference common labels (Form 10-K, Item numbers)
- Provide context about document purpose

### 6. Agent Management

Three separate extraction agents are created:
- `{deployment_name}-10k`
- `{deployment_name}-10q`
- `{deployment_name}-8k`

**Why Separate Agents?**
- Each agent can be independently updated
- Different schemas and system prompts
- Better tracking and monitoring per document type
- Allows for A/B testing of configurations

Agents are cached using `@functools.lru_cache` to avoid recreation on every request.

### 7. File Handling

#### Deduplication Strategy
Files are deduplicated using SHA-256 hash:
```python
file_content = Path(event.file_path).read_bytes()
file_hash = hashlib.sha256(file_content).hexdigest()
```

Before saving new data:
1. Search for existing data with same hash
2. Delete all matching items
3. Save new extraction result

This ensures reprocessing a file updates the data instead of duplicating.

#### Temporary File Management
- Downloaded files go to system temp directory
- Markdown temp files are created for classification
- Temp files are cleaned up in finally blocks
- Original files remain in cloud storage

## Common Pitfalls to Avoid

### ❌ DON'T: Use required fields in extraction schemas
```python
class Bad(BaseModel):
    revenue: str  # Will fail if LlamaExtract returns None
```

### ✅ DO: Use optional fields
```python
class Good(BaseModel):
    revenue: Optional[str]  # Handles None gracefully
```

### ❌ DON'T: Forget to set file metadata
```python
ExtractedData.create(data=final_data)  # Missing file_id, file_name, file_hash!
```

### ✅ DO: Always set complete metadata
```python
ExtractedData.create(
    data=final_data,
    file_id=event.file_id,
    file_name=event.filename,
    file_hash=file_hash,
)
```

### ❌ DON'T: Pass file path when you have markdown
```python
source_text = SourceText(file=event.file_path)  # Re-parses unnecessarily
```

### ✅ DO: Use markdown content directly
```python
source_text = SourceText(text_content=event.markdown_content)
```

### ❌ DON'T: Use complex nested dict types in schemas
```python
class Bad(BaseModel):
    data: dict[str, dict[str, Any]]  # LlamaExtract doesn't support this
```

### ✅ DO: Use simple types and lists
```python
class Good(BaseModel):
    events: Optional[list[Event8K]]  # Simple list of Pydantic models
```

## Testing Recommendations

1. **Test Each Document Type**: Ensure you have sample 10-K, 10-Q, and 8-K files
2. **Test Classification Confidence**: Check that confidence scores are reasonable
3. **Test Extraction Quality**: Verify extracted values match source documents
4. **Test Error Cases**: Try corrupted PDFs, wrong file types, empty documents
5. **Test Deduplication**: Upload same file twice and verify only one record exists

## Performance Considerations

- **Parsing**: Most expensive operation (~30-60 seconds per document)
- **Classification**: Fast (~2-5 seconds with markdown input)
- **Extraction**: Moderate (~10-20 seconds depending on document length)
- **Total**: Expect 1-2 minutes per document end-to-end

**Optimization Tips**:
- Use async operations throughout (all steps are async)
- Retry policies handle transient failures
- LRU caching prevents recreating clients
- Markdown reuse avoids duplicate parsing

## Future Enhancements

Potential improvements to consider:

1. **Parallel Extraction**: If a document has multiple sections, extract them in parallel
2. **Confidence Thresholds**: Reject low-confidence classifications for manual review
3. **Schema Versioning**: Track schema versions as extraction requirements evolve
4. **Validation Rules**: Add post-extraction validation (e.g., revenue > 0)
5. **Citation Tracking**: Enable cite_sources to track where data came from
6. **Reasoning Mode**: Enable use_reasoning for complex extraction cases

## Updating the Frontend

After modifying schemas, run:
```bash
uv run export-types
```

This regenerates TypeScript interfaces in `ui/src/schemas/` so the frontend stays in sync with the Python schemas.
