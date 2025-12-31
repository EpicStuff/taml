# TAML

YAML but with tabs

## Installation

```bash
pip install taml
```

## Usage

see [ruamel.yaml](https://yaml.readthedocs.io/en/latest/) and replace

```python
from ruamel.yaml import YAML
yaml=YAML()
```

with

```python
from taml import taml
```

## Note to self

- upload with `python -m build` then `python -m dotenv run -- twine upload --skip-existing dist/*`
