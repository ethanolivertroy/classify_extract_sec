import asyncio
import hashlib
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Literal

import httpx
from llama_cloud import ExtractRun
from llama_cloud.types import ClassifierRule
from llama_cloud_services.extract import SourceText
from llama_cloud_services.beta.agent_data import ExtractedData, InvalidExtractionData
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent
from workflows.retry_policy import ConstantDelayRetryPolicy

from .config import (
    get_llama_cloud_client,
    get_data_client,
    get_llama_parser,
    get_classify_client,
    get_extract_agent_for_10k,
    get_extract_agent_for_10q,
    get_extract_agent_for_8k,
)
from .schemas import MySchema, Form10KData, Form10QData, Form8KData

logger = logging.getLogger(__name__)


class FileEvent(StartEvent):
    file_id: str


class DownloadFileEvent(Event):
    file_id: str


class FileDownloadedEvent(Event):
    file_id: str
    file_path: str
    filename: str


class FileParsedEvent(Event):
    file_id: str
    file_path: str
    filename: str
    markdown_content: str


class FileClassifiedEvent(Event):
    file_id: str
    file_path: str
    filename: str
    markdown_content: str
    document_type: str  # "10-K", "10-Q", or "8-K"
    confidence: float


class UIToast(Event):
    level: Literal["info", "warning", "error"]
    message: str


class ExtractedEvent(Event):
    data: ExtractedData[MySchema]


class ExtractedInvalidEvent(Event):
    data: ExtractedData[dict[str, Any]]


class ProcessFileWorkflow(Workflow):
    """
    Given a file path, this workflow will process a single file through the custom extraction logic.
    """

    @step(retry_policy=ConstantDelayRetryPolicy(maximum_attempts=3, delay=10))
    async def run_file(self, event: FileEvent) -> DownloadFileEvent:
        logger.info(f"Running file {event.file_id}")
        return DownloadFileEvent(file_id=event.file_id)

    @step(retry_policy=ConstantDelayRetryPolicy(maximum_attempts=3, delay=10))
    async def download_file(
        self, event: DownloadFileEvent, ctx: Context
    ) -> FileDownloadedEvent:
        """Download the file reference from the cloud storage"""
        try:
            file_metadata = await get_llama_cloud_client().files.get_file(
                id=event.file_id
            )
            file_url = await get_llama_cloud_client().files.read_file_content(
                event.file_id
            )

            temp_dir = tempfile.gettempdir()
            filename = file_metadata.name
            file_path = os.path.join(temp_dir, filename)
            client = httpx.AsyncClient()
            # Report progress to the UI
            logger.info(f"Downloading file {file_url.url} to {file_path}")
            ctx.write_event_to_stream(
                UIToast(
                    level="info", message=f"Downloading file {filename}"
                )
            )

            async with client.stream("GET", file_url.url) as response:
                with open(file_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
            logger.info(f"Downloaded file {file_url.url} to {file_path}")
            return FileDownloadedEvent(
                file_id=event.file_id, file_path=file_path, filename=filename
            )
        except Exception as e:
            logger.error(f"Error downloading file {event.file_id}: {e}", exc_info=True)
            ctx.write_event_to_stream(
                UIToast(
                    level="error",
                    message=f"Error downloading file {event.file_id}: {e}",
                )
            )
            raise e

    @step(retry_policy=ConstantDelayRetryPolicy(maximum_attempts=3, delay=10))
    async def parse_document(
        self, event: FileDownloadedEvent, ctx: Context
    ) -> FileParsedEvent:
        """Parse the document using LlamaParse"""
        try:
            logger.info(f"Parsing document {event.filename}")
            ctx.write_event_to_stream(
                UIToast(
                    level="info", message=f"Parsing document {event.filename}"
                )
            )
            parser = get_llama_parser()
            parse_result = await parser.aparse(event.file_path)
            markdown_content = await parse_result.aget_markdown()

            logger.info(f"Successfully parsed document {event.filename}")
            ctx.write_event_to_stream(
                UIToast(
                    level="info", message=f"Successfully parsed document {event.filename}"
                )
            )

            return FileParsedEvent(
                file_id=event.file_id,
                file_path=event.file_path,
                filename=event.filename,
                markdown_content=markdown_content,
            )
        except Exception as e:
            logger.error(f"Error parsing document {event.filename}: {e}", exc_info=True)
            ctx.write_event_to_stream(
                UIToast(
                    level="error",
                    message=f"Error parsing document {event.filename}: {e}",
                )
            )
            raise e

    @step(retry_policy=ConstantDelayRetryPolicy(maximum_attempts=3, delay=10))
    async def classify_document(
        self, event: FileParsedEvent, ctx: Context
    ) -> FileClassifiedEvent:
        """Classify the document type (10-K, 10-Q, or 8-K)"""
        try:
            logger.info(f"Classifying document {event.filename}")
            ctx.write_event_to_stream(
                UIToast(
                    level="info", message=f"Classifying document {event.filename}"
                )
            )

            # Define classification rules
            rules = [
                ClassifierRule(
                    type="10-q",
                    description="Annual report filed by publicly traded companies, containing comprehensive financial information including audited annual financial statements, total revenue, net income, total assets, and total liabilities for the fiscal year. Typically labeled as Form 10-K or 10-K Annual Report."
                ),
                ClassifierRule(
                    type="10-k",
                    description="Quarterly report filed by publicly traded companies, containing unaudited financial statements for a specific quarter including quarterly revenue, quarterly net income, total assets, and total liabilities. Typically labeled as Form 10-Q or 10-Q Quarterly Report."
                ),
                ClassifierRule(
                    type="8-k",
                    description="Current report filed by publicly traded companies to announce major events or material changes, such as acquisitions, executive changes, earnings announcements, or other significant corporate events. Contains event descriptions organized by Item numbers (e.g., Item 1.01, Item 2.02). Typically labeled as Form 8-K or 8-K Current Report."
                )
            ]

            # Write markdown to temp file for classification
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(event.markdown_content)
                temp_path = Path(tmp.name)

            try:
                classifier = get_classify_client()
                classification_result = await classifier.aclassify_file_path(
                    rules=rules,
                    file_input_path=str(temp_path)
                )

                classification = classification_result.items[0].result
                document_type = classification.type
                confidence = classification.confidence or 0.0

                logger.info(
                    f"Document {event.filename} classified as {document_type} "
                    f"with confidence {confidence:.2%}"
                )
                ctx.write_event_to_stream(
                    UIToast(
                        level="info",
                        message=f"Document classified as {document_type} (confidence: {confidence:.2%})",
                    )
                )

                return FileClassifiedEvent(
                    file_id=event.file_id,
                    file_path=event.file_path,
                    filename=event.filename,
                    markdown_content=event.markdown_content,
                    document_type=document_type,
                    confidence=confidence,
                )
            finally:
                # Clean up temp file
                temp_path.unlink()

        except Exception as e:
            logger.error(f"Error classifying document {event.filename}: {e}", exc_info=True)
            ctx.write_event_to_stream(
                UIToast(
                    level="error",
                    message=f"Error classifying document {event.filename}: {e}",
                )
            )
            raise e

    @step(retry_policy=ConstantDelayRetryPolicy(maximum_attempts=3, delay=10))
    async def extract_data_based_on_type(
        self, event: FileClassifiedEvent, ctx: Context
    ) -> ExtractedEvent | ExtractedInvalidEvent:
        """Extract data based on the classified document type"""
        try:
            # track the content of the file, so as to be able to de-duplicate
            file_content = Path(event.file_path).read_bytes()
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Create source text from markdown content
            source_text = SourceText(
                text_content=event.markdown_content,
                filename=event.filename,
            )

            logger.info(
                f"Extracting data from {event.document_type} filing: {event.filename}"
            )
            ctx.write_event_to_stream(
                UIToast(
                    level="info",
                    message=f"Extracting data from {event.document_type} filing: {event.filename}",
                )
            )

            # Select the appropriate extraction agent based on document type
            if event.document_type == "10-k":
                agent = get_extract_agent_for_10k()
                extracted_result: ExtractRun = await agent.aextract(source_text)
                form_10k_data = Form10KData.model_validate(extracted_result.data)

                # Create final MySchema object with 10-K data
                final_data = MySchema(
                    document_type=event.document_type,
                    form_10k_data=form_10k_data,
                    form_10q_data=None,
                    form_8k_data=None,
                )

            elif event.document_type == "10-q":
                agent = get_extract_agent_for_10q()
                extracted_result: ExtractRun = await agent.aextract(source_text)

                print(f"Source Text: {source_text.text_content}")
                print(f"Extracted 10-Q data: {extracted_result.data}")

                form_10q_data = Form10QData.model_validate(extracted_result.data)

                # Create final MySchema object with 10-Q data
                final_data = MySchema(
                    document_type=event.document_type,
                    form_10k_data=None,
                    form_10q_data=form_10q_data,
                    form_8k_data=None,
                )

            elif event.document_type == "8-k":
                agent = get_extract_agent_for_8k()
                extracted_result: ExtractRun = await agent.aextract(source_text)
                form_8k_data = Form8KData.model_validate(extracted_result.data)

                # Create final MySchema object with 8-K data
                final_data = MySchema(
                    document_type=event.document_type,
                    form_10k_data=None,
                    form_10q_data=None,
                    form_8k_data=form_8k_data,
                )

            else:
                raise ValueError(f"Unknown document type: {event.document_type}")

            # Create ExtractedData object with MySchema
            extracted_data = ExtractedData.create(
                data=final_data,
                file_id=event.file_id,
                file_name=event.filename,
                file_hash=file_hash,
            )

            logger.info(f"Successfully extracted data from {event.document_type} filing")
            ctx.write_event_to_stream(
                UIToast(
                    level="info",
                    message=f"Successfully extracted data from {event.document_type} filing",
                )
            )

            return ExtractedEvent(data=extracted_data)

        except Exception as e:
            logger.error(
                f"Error extracting data from file {event.filename}: {e}",
                exc_info=True,
            )
            ctx.write_event_to_stream(
                UIToast(
                    level="error",
                    message=f"Error extracting data from file {event.filename}: {e}",
                )
            )
            raise e

    @step(retry_policy=ConstantDelayRetryPolicy(maximum_attempts=3, delay=10))
    async def record_extracted_data(
        self, event: ExtractedEvent | ExtractedInvalidEvent, ctx: Context
    ) -> StopEvent:
        """Records the extracted data to the agent data API"""
        try:
            logger.info(f"Recorded extracted data for file {event.data.file_name}")
            ctx.write_event_to_stream(
                UIToast(
                    level="info",
                    message=f"Recorded extracted data for file {event.data.file_name}",
                )
            )
            # remove past data when reprocessing the same file
            if event.data.file_hash:
                existing_data = await get_data_client().untyped_search(
                    filter={
                        "file_hash": {
                            "eq": event.data.file_hash,
                        },
                    },
                )
                if existing_data.items:
                    logger.info(
                        f"Removing past data for file {event.data.file_name} with hash {event.data.file_hash}"
                    )
                    await asyncio.gather(
                        *[
                            get_data_client().delete_item(item.id)
                            for item in existing_data.items
                        ]
                    )
            # finally, save the new data
            item_id = await get_data_client().create_item(event.data)
            return StopEvent(
                result=item_id.id,
            )
        except Exception as e:
            logger.error(
                f"Error recording extracted data for file {event.data.file_name}: {e}",
                exc_info=True,
            )
            ctx.write_event_to_stream(
                UIToast(
                    level="error",
                    message=f"Error recording extracted data for file {event.data.file_name}: {e}",
                )
            )
            raise e


workflow = ProcessFileWorkflow(timeout=None)

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    async def main():
        file = await get_llama_cloud_client().files.upload_file(
            upload_file=Path("test.pdf").open("rb")
        )
        await workflow.run(start_event=FileEvent(file_id=file.id))

    asyncio.run(main())
