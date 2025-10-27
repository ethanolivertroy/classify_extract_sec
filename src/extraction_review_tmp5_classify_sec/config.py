import functools
import os
import httpx

import dotenv
from llama_cloud_services import ExtractionAgent, LlamaExtract, LlamaParse
from llama_cloud_services.extract import ExtractConfig, ExtractMode
from llama_cloud.core.api_error import ApiError
from llama_cloud_services.beta.agent_data import AsyncAgentDataClient, ExtractedData
from llama_cloud_services.beta.classifier.client import ClassifyClient
from llama_cloud.client import AsyncLlamaCloud
from .schemas import MySchema, Form10KData, Form10QData, Form8KData

dotenv.load_dotenv()

# deployed agents may infer their name from the deployment name
# Note: Make sure that an agent deployment with this name actually exists
# otherwise calls to get or set data will fail. You may need to adjust the `or `
# name for development
agent_name = os.getenv("LLAMA_DEPLOY_DEPLOYMENT_NAME")
agent_name_or_default = agent_name or "extraction-review-tmp5-classify-sec"
# required for all llama cloud calls
api_key = os.environ["LLAMA_CLOUD_API_KEY"]
# get this in case running against a different environment than production
base_url = os.getenv("LLAMA_CLOUD_BASE_URL")
extracted_data_collection = "extraction-review-tmp5-classify-sec"
project_id = os.getenv("LLAMA_DEPLOY_PROJECT_ID")


@functools.lru_cache(maxsize=None)
def get_extract_agent() -> ExtractionAgent:
    extract_api = LlamaExtract(
        api_key=api_key, base_url=base_url, project_id=project_id
    )
    config = ExtractConfig(
        extraction_mode=ExtractMode.PREMIUM,
        system_prompt=None,
        # advanced
        use_reasoning=False,
        cite_sources=False,
        confidence_scores=True,
    )
    try:
        existing = extract_api.get_agent(agent_name_or_default)
        existing.data_schema = MySchema
        existing.config = config
        return existing
    except ApiError as e:
        if e.status_code == 404:
            return extract_api.create_agent(
                name=agent_name_or_default, data_schema=MySchema, config=config
            )
        else:
            raise


@functools.lru_cache(maxsize=None)
def get_data_client() -> AsyncAgentDataClient:
    return AsyncAgentDataClient(
        deployment_name=agent_name,
        collection=extracted_data_collection,
        # update MySchema for your schema, but retain the ExtractedData container
        type=ExtractedData[MySchema],
        client=get_llama_cloud_client(),
    )


@functools.lru_cache(maxsize=None)
def get_llama_cloud_client():
    return AsyncLlamaCloud(
        base_url=base_url,
        token=api_key,
        httpx_client=httpx.AsyncClient(
            timeout=60, headers={"Project-Id": project_id} if project_id else None
        ),
    )


@functools.lru_cache(maxsize=None)
def get_llama_parser() -> LlamaParse:
    """Get LlamaParse client for parsing PDFs"""
    return LlamaParse(
        parse_mode="parse_page_with_agent",
        model="openai-gpt-4-1-mini",
        high_res_ocr=True,
        adaptive_long_table=True,
        outlined_table_extraction=True,
        output_tables_as_HTML=True,
        result_type="markdown",
        project_id=project_id,
    )


@functools.lru_cache(maxsize=None)
def get_classify_client() -> ClassifyClient:
    """Get ClassifyClient for document classification"""
    return ClassifyClient.from_api_key(api_key)


@functools.lru_cache(maxsize=None)
def get_extract_agent_for_10k() -> ExtractionAgent:
    """Get extraction agent for 10-K filings"""
    extract_api = LlamaExtract(
        api_key=api_key, base_url=base_url, project_id=project_id
    )
    config = ExtractConfig(
        extraction_mode=ExtractMode.PREMIUM,
        system_prompt="Extract financial data from this 10-K annual report.",
        use_reasoning=False,
        cite_sources=False,
        confidence_scores=True,
    )
    agent_name_10k = f"{agent_name_or_default}-10k"
    try:
        existing = extract_api.get_agent(agent_name_10k)
        existing.data_schema = Form10KData
        existing.config = config
        return existing
    except ApiError as e:
        if e.status_code == 404:
            return extract_api.create_agent(
                name=agent_name_10k, data_schema=Form10KData, config=config
            )
        else:
            raise


@functools.lru_cache(maxsize=None)
def get_extract_agent_for_10q() -> ExtractionAgent:
    """Get extraction agent for 10-Q filings"""
    extract_api = LlamaExtract(
        api_key=api_key, base_url=base_url, project_id=project_id
    )
    config = ExtractConfig(
        extraction_mode=ExtractMode.PREMIUM,
        system_prompt="Extract quarterly financial data from this 10-Q quarterly report.",
        use_reasoning=False,
        cite_sources=False,
        confidence_scores=True,
    )
    agent_name_10q = f"{agent_name_or_default}-10q"
    try:
        existing = extract_api.get_agent(agent_name_10q)
        existing.data_schema = Form10QData
        existing.config = config
        return existing
    except ApiError as e:
        if e.status_code == 404:
            return extract_api.create_agent(
                name=agent_name_10q, data_schema=Form10QData, config=config
            )
        else:
            raise


@functools.lru_cache(maxsize=None)
def get_extract_agent_for_8k() -> ExtractionAgent:
    """Get extraction agent for 8-K filings"""
    extract_api = LlamaExtract(
        api_key=api_key, base_url=base_url, project_id=project_id
    )
    config = ExtractConfig(
        extraction_mode=ExtractMode.PREMIUM,
        system_prompt="Extract all events from this 8-K current report, including the event category (Item number) and description.",
        use_reasoning=False,
        cite_sources=False,
        confidence_scores=True,
    )
    agent_name_8k = f"{agent_name_or_default}-8k"
    try:
        existing = extract_api.get_agent(agent_name_8k)
        existing.data_schema = Form8KData
        existing.config = config
        return existing
    except ApiError as e:
        if e.status_code == 404:
            return extract_api.create_agent(
                name=agent_name_8k, data_schema=Form8KData, config=config
            )
        else:
            raise
