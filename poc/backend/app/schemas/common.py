from typing import TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class PaginationQuery(BaseModel):
    page: int = 1
    page_size: int = 20

    model_config = ConfigDict(str_strip_whitespace=True)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class ErrorDetail(BaseModel):
    code: str
    message: str
