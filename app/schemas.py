from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SeriesIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    volume: int | None = None
    publisher: str | None = None
    last_number: int = Field(ge=0, default=1)
    notes: str | None = None


class SeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    volume: int | None
    publisher: str | None
    last_number: int
    notes: str | None
    created_at: datetime
    next_number: int


class CheckResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    series_id: int
    checked_at: datetime
    number_searched: int
    status: str
    url: str | None
    result_title: str | None
    price: float | None
    message: str | None


class CheckStatusUpdate(BaseModel):
    # El usuario confirma un "posible" como disponible tras verlo en Amazon,
    # o lo descarta como falso positivo (no_encontrado).
    status: Literal["disponible", "no_encontrado"]


class SeriesWithLastCheckOut(SeriesOut):
    last_check: CheckResultOut | None = None


class CheckAllResponse(BaseModel):
    results: list[CheckResultOut]
    errors: list[str] = Field(default_factory=list)


class ImportColumn(BaseModel):
    file_column: str
    target_field: str


class ImportPreview(BaseModel):
    columns: list[str]
    rows: list[dict]
    suggested_mapping: dict[str, str]


class ImportResult(BaseModel):
    created: int
    skipped: list[str] = Field(default_factory=list)