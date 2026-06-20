from pydantic import BaseModel, HttpUrl


class ReportRequest(BaseModel):
    website: HttpUrl

