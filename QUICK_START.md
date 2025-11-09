# Quick Start Guide

## Prerequisites

1. **Environment Variables**
   ```bash
   export LLAMA_CLOUD_API_KEY="llx-..."
   export LLAMA_DEPLOY_PROJECT_ID="your-project-id"
   ```

2. **Install Dependencies**
   ```bash
   uv sync
   ```

## Running the Workflow

### Option 1: Via Main Script (Testing)
```bash
cd /path/to/extraction-review-tmp5-classify-sec
python -m src.extraction_review_tmp5_classify_sec.process_file
```

Note: Update the `test.pdf` in the `main()` function to point to your SEC filing.

### Option 2: Via UI (Production)
1. Start the backend:
   ```bash
   uv run llama-deploy run
   ```

2. Start the frontend:
   ```bash
   cd ui
   npm install
   npm run dev
   ```

3. Open browser to `http://localhost:3000`

4. Upload an SEC filing (10-K, 10-Q, or 8-K PDF)

## Testing with Sample Files

### Test 10-K (Annual Report)
- Look for: Annual financial statements, fiscal year data
- Expected output: `form_10k_data` populated with total_revenue, net_income, etc.

### Test 10-Q (Quarterly Report)
- Look for: Quarterly financial statements, "three months ended"
- Expected output: `form_10q_data` populated with quarterly_revenue, quarterly_net_income, etc.

### Test 8-K (Current Report)
- Look for: Event disclosures, Item numbers (e.g., Item 2.02, Item 5.02)
- Expected output: `form_8k_data` populated with list of events

## Monitoring Workflow Progress

### Via Logs
```bash
# Set log level to INFO
export LOG_LEVEL=INFO

# Run workflow and watch logs
uv run python -m src.extraction_review_tmp5_classify_sec.process_file
```

Look for key log messages:
- `"Downloading file..."`
- `"Parsing document..."`
- `"Classifying document..."`
- `"Document classified as {type} with confidence {X}%"`
- `"Extracting data from {type} filing..."`
- `"Successfully extracted data..."`
- `"Recorded extracted data..."`

### Via UI
The UI displays toast notifications for each step:
- ℹ️ Info: Progress updates
- ⚠️ Warning: Non-critical issues
- ❌ Error: Failures requiring attention

## Viewing Results

### Via Agent Data API
```python
from src.extraction_review_tmp5_classify_sec.config import get_data_client

# List all extracted data
client = get_data_client()
results = await client.untyped_search()

for item in results.items:
    print(f"File: {item.data['file_name']}")
    print(f"Type: {item.data['data']['document_type']}")
    print(f"Data: {item.data['data']}")
```

### Via UI
1. Navigate to the review interface
2. See list of processed files with:
   - Document type (10-K/10-Q/8-K)
   - Extracted data
   - Confidence scores
3. Click on any item to review/edit

## Troubleshooting

### Error: "Agent not found"
**Solution**: The extraction agents are created automatically on first run. Wait for initialization.

### Error: "Failed to parse document"
**Possible causes**:
- Invalid PDF file
- Corrupted upload
- Network timeout

**Solution**: Check file is valid PDF, retry upload, increase timeout.

### Error: "Classification confidence too low"
**Possible causes**:
- Document is not a standard SEC filing
- Document has unusual format
- Document is heavily redacted

**Solution**: Review classification rules, consider manual classification.

### Error: "Extraction validation failed"
**Possible causes**:
- LlamaExtract returned None for required field (shouldn't happen with Optional fields)
- Schema mismatch

**Solution**: Check that all schema fields are Optional.

### Extraction returns empty/null values
**Possible causes**:
- Document doesn't contain expected data
- Data is in unexpected format
- System prompt needs refinement

**Solution**:
1. Review source document
2. Check extraction agent system prompts
3. Consider adjusting extraction mode (MULTIMODAL vs PREMIUM)

## Performance Tips

1. **First Run is Slower**: Agent creation and model loading happens on first request
2. **Subsequent Runs are Faster**: Agents are cached, models are warm
3. **Large Documents**: Increase timeout if processing very large filings (>100 pages)
4. **Batch Processing**: Process multiple files by uploading them all at once

## Updating the Schema

1. **Modify** `src/extraction_review_tmp5_classify_sec/schemas.py`
2. **Update** extraction agents in `config.py` if needed
3. **Regenerate** TypeScript types:
   ```bash
   uv run export-types
   ```
4. **Restart** both backend and frontend

## Getting Help

- Check logs for detailed error messages
- Review `IMPLEMENTATION_NOTES.md` for common pitfalls
- Verify environment variables are set correctly
- Ensure LlamaCloud API key has sufficient permissions

## Example: Complete Test Flow

```bash
# 1. Set up environment
export LLAMA_CLOUD_API_KEY="llx-..."
export LLAMA_DEPLOY_PROJECT_ID="your-project-id"

# 2. Install dependencies
uv sync

# 3. Create test script
cat > test_workflow.py << 'EOF'
import asyncio
import logging
from pathlib import Path
from src.extraction_review_tmp5_classify_sec.process_file import workflow, FileEvent
from src.extraction_review_tmp5_classify_sec.config import get_llama_cloud_client

logging.basicConfig(level=logging.INFO)

async def test():
    # Upload test file
    file = await get_llama_cloud_client().files.upload_file(
        upload_file=Path("test-10k.pdf").open("rb")
    )
    print(f"Uploaded file: {file.id}")

    # Run workflow
    result = await workflow.run(start_event=FileEvent(file_id=file.id))
    print(f"Workflow completed with result: {result}")

asyncio.run(test())
EOF

# 4. Run test
python test_workflow.py

# 5. Check results
# - Look for "Document classified as 10-K" in logs
# - Verify extraction completed successfully
# - Check data was recorded to Agent Data API
```

## Next Steps

After verifying the workflow works:

1. **Customize System Prompts**: Adjust prompts in `config.py` for your specific needs
2. **Add Validation**: Implement post-extraction validation rules
3. **Extend Schema**: Add additional fields to extraction schemas as needed
4. **Configure UI**: Customize the review interface for your use case
5. **Deploy**: Use `llama-deploy` to deploy to production
