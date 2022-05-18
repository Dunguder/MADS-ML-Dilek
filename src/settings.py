from pydantic import BaseModel, root_validator
from typing import Optional, Union, Dict
from pathlib import Path
from ray import tune
SAMPLE_INT = tune.sample.Integer
SAMPLE_FLOAT = tune.sample.Float

class BaseSearchSpace(BaseModel):
    input_size: int
    output_size: int
    tune_dir : Optional[Path]
    data_dir : Path
    class Config:
        arbitrary_types_allowed = True

    @root_validator
    def check_path(cls, values: Dict) -> Dict:  # noqa: N805
        datadir = values.get("data_dir")
        if not datadir.exists():
            raise FileNotFoundError(
                f"Make sure the datadir exists.\n Found {datadir} to be non-existing."
            )
        return values

class SearchSpace(BaseSearchSpace):
    hidden_size:  Union[int, SAMPLE_INT] = tune.randint(16, 128)
    dropout: Union[float, SAMPLE_FLOAT] = tune.uniform(0.0, 0.3)
    num_layers: Union[int, SAMPLE_INT] = tune.randint(2, 5)