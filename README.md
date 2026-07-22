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

## Additional Features

you can use a separate taml file or dict to type the taml

```yaml
a:
	a: 3
	b: 956579776
	c:
		- 1
		- 2
		- 3
	d:
		- 1.12345
		- 2
		- {'a': 1}
		- 4
```

and

```yaml
a:
	b: datetime.datetime.fromtimestamp(tz=datetime.timezone.utc)
	c: tuple
	d:
		- round(ndigits=2)
		- null
		- epicstuff.Dict(b='1')  # make sure b stays str during resolve
		- str
```

## Note to self

- upload with `python -m build` then `python -m dotenv run -- twine upload --skip-existing dist/*`

## Todo:
0. ~~handle schema ceoversion fail errer~~
1. ~~add line and col to exceptions~~
2. ask ai for missing json schema features
3. ask ai for suggestions
4. update readme with schema info
5. maybe add taml.default