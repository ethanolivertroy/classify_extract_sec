from pydantic import BaseModel, Field
from typing import Optional


# Schema for 10-K filings
class Form10KData(BaseModel):
    total_revenue: Optional[str] = Field(
        None, description="Total revenue for the fiscal year"
    )
    net_income: Optional[str] = Field(None, description="Net income for the fiscal year")
    total_assets: Optional[str] = Field(
        None, description="Total assets at the end of the fiscal year"
    )
    total_liabilities: Optional[str] = Field(
        None, description="Total liabilities at the end of the fiscal year"
    )


# Schema for 10-Q filings
class Form10QData(BaseModel):
    quarterly_revenue: Optional[str] = Field(
        None, description="Revenue for the quarter"
    )
    quarterly_net_income: Optional[str] = Field(
        None, description="Net income for the quarter"
    )
    total_assets: Optional[str] = Field(
        None, description="Total assets at the end of the quarter"
    )
    total_liabilities: Optional[str] = Field(
        None, description="Total liabilities at the end of the quarter"
    )


# Schema for individual event in 8-K filings
class Event8K(BaseModel):
    category: Optional[str] = Field(
        None, description="Category of the event (e.g., Item 1.01, Item 2.02)"
    )
    description: Optional[str] = Field(
        None, description="Description of the event reported in the 8-K"
    )


# Schema for 8-K filings
class Form8KData(BaseModel):
    events: Optional[list[Event8K]] = Field(
        None, description="List of events reported in the 8-K filing"
    )


# Final output schema that contains the classification and extracted data
class MySchema(BaseModel):
    document_type: Optional[str] = Field(
        None, description="Type of SEC filing (10-K, 10-Q, or 8-K)"
    )
    form_10k_data: Optional[Form10KData] = Field(
        None, description="Extracted data for 10-K filings"
    )
    form_10q_data: Optional[Form10QData] = Field(
        None, description="Extracted data for 10-Q filings"
    )
    form_8k_data: Optional[Form8KData] = Field(
        None, description="Extracted data for 8-K filings"
    )
