from pydantic import BaseModel, ConfigDict, Field


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dataset_id: str = Field(pattern=r"^ds_[a-f0-9]{32}$")
    label_column: str | None = Field(default=None, max_length=200)
    max_rounds: int = Field(default=6, ge=1, le=20)
    use_llm: bool = True
