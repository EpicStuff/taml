import ast, builtins, contextlib
from collections.abc import Callable, MutableMapping, Mapping, MutableSequence, Sequence
from dataclasses import dataclass
from typing import Any

from epicstuff import wrap, NewDict as Dict
from ruamel.yaml import YAMLError
from zope.dottedname.resolve import resolve as zresolve


class schema: ...
@dataclass
class required(schema):
	'Indicates value is required.'

	path: Any; _: int; __: int; func: Callable | None = None

	def __call__(self, data: Any, line: int, col: int) -> Any:
		if data is None:
			raise RequiredError(self.path, line, col)
		if self.func:
			return self.func(data)
		return data
class strict(schema):
	'Checks if value type is correct instead of converting.'

	def __init__(self, path: Any, line: int, col: int, func: Callable | None = None) -> None:
		'Make sure that func exists.'
		if func is None:
			raise SchemaDefinitionError(f'Missing arguments for strict (line {line+1}, col {col+1})')
		if isinstance(func, required) and func.func is None:
			raise SchemaDefinitionError(f'Missing arguments for required inside strict (line {line+1}, col {col+1})')

		self.path: str = path; self.func: Callable = func

	def __call__(self, data: Any, line: int, col: int) -> Any:
		# do required check first
		func: Callable = self.func
		if isinstance(self.func, required):
			func = self.func.func  # pyright: ignore[reportAssignmentType]
			if data is None:
				self.func(data, line, col)

		if data is not None:
			if not isinstance(data, func):
				raise StrictError(func, data, line, col)
			return func(data)
		return data
class repeat(schema): ...

class SchemaError(YAMLError): ...
class RequiredError(SchemaError, ValueError):
	def __init__(self, path: str, line: int, col: int) -> None:
		assert path, 'look into this'
		super().__init__(f'{path} is required (line {line+1}, col {col+1})')
class StrictError(SchemaError, TypeError):
	def __init__(self, expected: Any, data: Any, line: int, col: int) -> None:
		super().__init__(f'Expected {expected.__name__}, got {type(data).__name__}: {data!r} (line {line+1}, col {col+1})')
class StructureError(SchemaError, TypeError):
	def __init__(self, mapping: bool, data: Any, line: int, col: int) -> None:
		t = 'MutableMapping' if mapping else 'MutableSequence'
		super().__init__(f'Expected {t} or None, got {type(data).__name__}: {data!r} (line {line+1}, col {col+1})')
class SchemaDefinitionError(SchemaError, ValueError): ...

class SchemaImportError(SchemaError, ImportError): ...  # pyright: ignore[reportUnsafeMultipleInheritance]
class ConversionTypeError(SchemaError, TypeError):
	def __init__(self, schema: Callable, data: Any, line: int, col: int) -> None:
		super().__init__(f'Cannot convert {data!r} to {schema.__name__} (line {line+1}, col {col+1})')
class ConversionValueError(SchemaError, ValueError):
	def __init__(self, schema: Callable, data: Any, line: int, col: int) -> None:
		super().__init__(f'Cannot convert {data!r} to {schema.__name__} (line {line+1}, col {col+1})')

def _format_schema(schema: Dict | Any, line: int | None = None, col: int | None = None, path: str | None = None) -> Any | None:
	path = path or ''
	# if schema value is a list, call self on each item
	if isinstance(schema, MutableSequence):
		for num, item in enumerate(schema):
			schema[num] = _format_schema(item, *schema.lc.item(num), path=f'{path}[{num}]')
	# if schema value is a dict, call self on each value and deal with key
	if isinstance(schema, MutableMapping):
		for key, value in schema.items():
			# todo: go through this part
			if 'taml.repeat' in key:
				idx = list(schema).index(key)
				val = schema.pop(key)
				new = _resolve(key, *schema.lc.key(key), path=path)
				schema.insert(idx, new, val)
				if key in schema.ca.items:
					schema.ca.items[new] = schema.ca.items.pop(key)

			schema[key] = _format_schema(value, *schema.lc.value(key), path=f'{path}.{key}')
	# if is a str, turn into object
	if isinstance(schema, str):
		return _resolve(schema, line, col, path.lstrip('.'))  # pyright: ignore[reportArgumentType]
	# else
	return schema
def _resolve(src: str, line: int, col: int, path: str) -> Any:
	'Convert a string like epicstuff.Dict to a Dict object.'
	def node_to_value(src: str, node: ast.AST) -> Any:
		'Convert ast node to python object.'
		# convert if is numbers, strings, bools, and None
		if isinstance(node, ast.Constant):
			return node.value
		# convert if is literals (lists, dicts, etc.)
		with contextlib.suppress(Exception):
			return ast.literal_eval(node)

		# else, convert the node to string
		seg = ast.get_source_segment(src, node) #or ast.unparse(node)
		# make sure is not stuff like 1 + 2 (ast.BinOp), a if cond else b (ast.IfExp), etc.
		if isinstance(node, (ast.Name, ast.Attribute, ast.Call)):
			assert node.lineno == 1, 'look into this'
			return _resolve(seg, line, col + node.col_offset, path)
		assert hasattr(node, 'col_offset'), 'look into this'
		raise SchemaDefinitionError(f'Unsupported expression {seg!r} (line {line+1}, col {col + node.col_offset+1})')  # pyright: ignore[reportAttributeAccessIssue]
	resolved_args = []
	resolved_kwargs = {}

	src = src.strip()
	parsed = ast.parse(src, mode='eval').body

	# resolve args first
	## if is callable (eg. func(args), func with brackets)
	if isinstance(parsed, ast.Call):
		# get func as string
		func = ast.get_source_segment(src, parsed.func) #or ast.unparse(parsed.func)
		# get each arg
		resolved_args.extend(node_to_value(src, arg) for arg in parsed.args)
		# get each kwarg
		for kwarg in parsed.keywords:
			# reject unpacking
			if kwarg.arg is None:
				raise SchemaDefinitionError(f'Keyword argument must be written as name=value (line {line + 1}, col {col + kwarg.col_offset + 1})')
			resolved_kwargs[kwarg.arg] = node_to_value(src, kwarg.value)
	## else, just a func without brackets, like int or epicstuff.Dict
	else:
		func = src

	# resolve func
	## try builtins first
	if hasattr(builtins, func):
		func = getattr(builtins, func)
		return wrap(func, *resolved_args, **resolved_kwargs) if resolved_args or resolved_kwargs else func
	## resolve if not builtin
	try:
		func = zresolve(func)
	except ImportError as e:
		raise SchemaImportError(f'{e} (line {line+1}, col {col+1})') from e
	## special stuff for required and strict
	if func in (required, strict):
		return func(path, line, col, *resolved_args, **resolved_kwargs)
	## else, wrap func with args
	return wrap(func, *resolved_args, **resolved_kwargs) if resolved_args or resolved_kwargs else func

def _format_data(data: Any, schema: Any, line: int = 0, col: int = 0, p_line: int = 0, p_col: int = 0) -> Any:
	# if the schema value is a dict
	if isinstance(schema, Mapping):
		# data value has to be a dict or none
		if not isinstance(data, MutableMapping) and data is not None:
			raise StructureError(True, data, line, col)
		# go through each item in schema, and run format on it and matching data value
		for s_key, s_value in schema.items():
			# if key does not exist in data, pass None and parent key line/col to self
			if data is None or s_key not in data:
				_format_data(None, s_value, p_line, p_col, p_line, p_col)
			else:
				data[s_key] = _format_data(data.get(s_key), s_value, *data.lc.value(s_key), *data.lc.key(s_key))
	# if the schema value is list
	elif isinstance(schema, (list | tuple | set | frozenset)):
		# data value has to be a list or none
		if not isinstance(data, MutableSequence) and data is not None:
			raise StructureError(False, data, line, col)
		# go through each item in schema, and run format on it and each item in data
		for num, s_value in enumerate(schema):
			# if index does not exist in data, pass None and parent key line/col to self
			if data is None or num >= len(data):
				_format_data(None, s_value, p_line, p_col, p_line, p_col)
			else:
				data[num] = _format_data(data[num], s_value, *data.lc.item(num), *data.lc.item(num))

	# format the value
	elif isinstance(schema, (required, strict)):
		return schema(data, line, col)
	elif callable(schema) and data is not None:
		try:
			return schema(data)
		except TypeError as e:
			raise ConversionTypeError(schema, data, line, col) from e
		except ValueError as e:
			raise ConversionValueError(schema, data, line, col) from e
	return data
