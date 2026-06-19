import ast, builtins, contextlib
from collections.abc import Callable, MutableMapping, Mapping, MutableSequence
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

	def __call__(self, data: Any, line: int, col: int, path: str | None = None) -> Any:
		if data is None:
			raise RequiredError(path or self.path, line, col)
		if self.func:
			return self.func(data)
		return data
class strict(schema):
	'Checks if value type is correct instead of converting.'

	def __init__(self, path: Any, line: int, col: int, func: Callable | None = None) -> None:
		'Make sure that func exists.'
		loc = f' at {path}' if path else ''
		if func is None:
			raise SchemaDefinitionError(f'Missing arguments for strict{loc} (line {line + 1}, col {col + 1})')
		if isinstance(func, required) and func.func is None:
			raise SchemaDefinitionError(f'Missing arguments for required inside strict{loc} (line {line + 1}, col {col + 1})')

		self.path: str = path; self.func: Callable = func

	def __call__(self, data: Any, line: int, col: int, path: str | None = None) -> Any:
		# do required check first
		func: Callable = self.func
		if isinstance(self.func, required):
			func = self.func.func  # pyright: ignore[reportAssignmentType]
			if data is None:
				self.func(data, line, col, path=path)

		if data is not None:
			if not isinstance(data, func):
				raise StrictError(func, data, line, col)
			return func(data)
		return data
@dataclass(eq=False)
class repeat(schema):
	r'''Used to define properties of multiple keys or values.

	Can be used as a key, eg. `taml.repeat(): X` which would equal to `taml.repeat(): X\ntaml.repeat(): X\n...` where X is some schema definition.
	Or can be used in a list, eg. `key: taml.repeat(X)` or `key: [taml.repeat(X)]` where X gets applied to each value of list.

	Args:
		`coerce: bool = True`: turns null data into the empty collection, eg.: `key: ` -> `key: []`

	'''

	schema: Callable | None = None; coerce: bool = True
@dataclass
class coerce(schema):
	'''Apply ``func`` to the value even when it is None.

	Plain callables are skipped on null/missing values so a schema never
	coerces an absent field. Wrap the callable in ``taml.coerce`` when the
	converter itself knows how to handle None (e.g. turning null into an
	empty list), so it runs on an explicit ``null`` too.
	'''

	func: Callable | None = None

	def __call__(self, data: Any, line: int, col: int, path: str | None = None) -> Any:
		if self.func is None:
			return data
		try:
			return self.func(data)
		except TypeError as e:
			raise ConversionTypeError(self.func, data, line, col) from e
		except ValueError as e:
			raise ConversionValueError(self.func, data, line, col) from e

class SchemaError(YAMLError): ...
class RequiredError(SchemaError, ValueError):
	def __init__(self, path: str, line: int, col: int) -> None:
		assert path, 'look into this'
		super().__init__(f'{path} is required (line {line + 1}, col {col + 1})')
class StrictError(SchemaError, TypeError):
	def __init__(self, expected: Any, data: Any, line: int, col: int) -> None:
		super().__init__(f'Expected {expected.__name__}, got {type(data).__name__}: {data!r} (line {line + 1}, col {col + 1})')
class StructureError(SchemaError, TypeError):
	def __init__(self, mapping: bool, data: Any, line: int, col: int) -> None:
		t = 'dict' if mapping else 'list'
		super().__init__(f'Expected {t} or None, got {type(data).__name__}: {data!r} (line {line + 1}, col {col + 1})')
class SchemaDefinitionError(SchemaError, ValueError): ...

class SchemaImportError(SchemaError, ImportError): ...  # pyright: ignore[reportUnsafeMultipleInheritance]
class ConversionTypeError(SchemaError, TypeError):
	def __init__(self, schema: Callable, data: Any, line: int, col: int) -> None:
		try:
			name = schema.__name__
		except AttributeError:
			name = schema
		super().__init__(f'Cannot convert {data!r} to {name} (line {line + 1}, col {col + 1})')
class ConversionValueError(SchemaError, ValueError):
	def __init__(self, schema: Callable, data: Any, line: int, col: int) -> None:
		super().__init__(f'Cannot convert {data!r} to {schema.__name__} (line {line + 1}, col {col + 1})')

def _format_schema(schema: Dict | Any, line: int | None = None, col: int | None = None, path: str | None = None) -> Any | None:
	path = path or ''
	# if schema value is a list, call self on each item
	if isinstance(schema, MutableSequence):
		for num, item in enumerate(schema):
			schema[num] = _format_schema(item, *schema.lc.item(num), path=f'{path}[{num}]')
	# if schema value is a dict, call self on each value and deal with key
	if isinstance(schema, MutableMapping):
		# capture lc info before mutating keys, since lc lookups don't survive rename
		items = []
		for key in list(schema):
			v_line, v_col = schema.lc.value(key)
			if isinstance(key, str) and 'taml.repeat' in key:
				k_line, k_col = schema.lc.key(key)
				new_key = _resolve(key, k_line, k_col, path=path)
				new_path = f'{path}[*]'
				if isinstance(new_key, repeat) and new_key.schema is not None:
					raise SchemaDefinitionError(f'taml.repeat used as a key cannot take a schema argument at {new_path} (line {k_line + 1}, col {k_col + 1})')
				if schema[key] is None:
					raise SchemaDefinitionError(f'taml.repeat used as a key requires a nested schema at {new_path} (line {k_line + 1}, col {k_col + 1})')
			else:
				new_key = key
				new_path = f'{path}.{key}' if path else str(key)
			items.append((key, new_key, schema[key], v_line, v_col, new_path))
		for old_key, new_key, value, v_line, v_col, new_path in items:
			if old_key is not new_key:
				idx = list(schema).index(old_key)
				schema.pop(old_key)
				schema.insert(idx, new_key, value)
				if old_key in schema.ca.items:
					schema.ca.items[new_key] = schema.ca.items.pop(old_key)
			schema[new_key] = _format_schema(value, v_line, v_col, path=new_path)
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
		seg = ast.get_source_segment(src, node)  # or ast.unparse(node)
		# make sure is not stuff like 1 + 2 (ast.BinOp), a if cond else b (ast.IfExp), etc.
		if isinstance(node, (ast.Name, ast.Attribute, ast.Call)):
			assert node.lineno == 1, 'look into this'
			return _resolve(seg, line, col + node.col_offset, path)
		assert hasattr(node, 'col_offset'), 'look into this'
		loc = f' at {path}' if path else ''
		raise SchemaDefinitionError(f'Unsupported expression {seg!r}{loc} (line {line + 1}, col {col + node.col_offset + 1})')  # pyright: ignore[reportAttributeAccessIssue]
	resolved_args = []
	resolved_kwargs = {}

	src = src.strip()
	parsed = ast.parse(src, mode='eval').body

	# resolve args first
	## if is callable (eg. func(args), func with brackets)
	if isinstance(parsed, ast.Call):
		# get func as string
		func = ast.get_source_segment(src, parsed.func)  # or ast.unparse(parsed.func) #@IgnoreException
		# get each arg
		resolved_args.extend(node_to_value(src, arg) for arg in parsed.args)
		# get each kwarg
		for kwarg in parsed.keywords:
			# reject unpacking
			if kwarg.arg is None:
				loc = f' at {path}' if path else ''
				raise SchemaDefinitionError(f'Keyword argument must be written as name=value{loc} (line {line + 1}, col {col + kwarg.col_offset + 1})')
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
		loc = f' at {path}' if path else ''
		raise SchemaImportError(f'{e}{loc} (line {line + 1}, col {col + 1})') from e
	## special stuff for required and strict
	if func in (required, strict):
		return func(path, line, col, *resolved_args, **resolved_kwargs)
	## repeat and coerce always become an instance, even with no args
	if func in (repeat, coerce):
		return func(*resolved_args, **resolved_kwargs)
	## else, wrap func with args
	return wrap(func, *resolved_args, **resolved_kwargs) if resolved_args or resolved_kwargs else func

def _format_data(data: Any, schema: Any, line: int = 0, col: int = 0, p_line: int = 0, p_col: int = 0, path: str = '') -> Any:
	# if the schema value is a dict
	if isinstance(schema, Mapping):
		# data value has to be a dict or none
		if not isinstance(data, MutableMapping) and data is not None:
			raise StructureError(True, data, line, col)
		# split schema keys into static keys and an optional repeat schema
		repeat_key: repeat | None = None
		repeat_schema: Any = None
		static_keys: list = []
		for s_key in schema:
			if isinstance(s_key, repeat):
				repeat_key = s_key
				repeat_schema = schema[s_key]
			else:
				static_keys.append(s_key)
		# coerce None to an empty dict when the repeat marker opts in
		if data is None and repeat_key is not None and repeat_key.coerce:
			data = Dict()
		# process each statically-named schema key
		for s_key in static_keys:
			s_value = schema[s_key]
			new_path = f'{path}.{s_key}' if path else str(s_key)
			# if key does not exist in data, pass None and parent key line/col to self
			if data is None or s_key not in data:
				_format_data(None, s_value, p_line, p_col, p_line, p_col, path=new_path)
			else:
				data[s_key] = _format_data(data.get(s_key), s_value, *data.lc.value(s_key), *data.lc.key(s_key), path=new_path)
		# if there is a repeat schema, apply it to remaining data keys
		if repeat_schema is not None and data is not None:
			for d_key in list(data):
				if d_key in static_keys:
					continue
				new_path = f'{path}.{d_key}' if path else str(d_key)
				data[d_key] = _format_data(data[d_key], repeat_schema, *data.lc.value(d_key), *data.lc.key(d_key), path=new_path)
	# if the schema value is list
	elif isinstance(schema, (list | tuple | set | frozenset)):
		# data value has to be a list or none
		if not isinstance(data, MutableSequence) and data is not None:
			raise StructureError(False, data, line, col)
		# locate a repeat marker (first occurrence wins)
		repeat_marker: repeat | None = None
		repeat_idx: int | None = None
		for num, s_value in enumerate(schema):
			if isinstance(s_value, repeat):
				repeat_marker = s_value
				repeat_idx = num
				break
		# coerce None to an empty list when the repeat marker opts in
		if data is None and repeat_marker is not None and repeat_marker.coerce:
			data = []
		# process static prefix (everything before the repeat marker, or all of schema if none)
		prefix_end = repeat_idx if repeat_idx is not None else len(schema)
		for num in range(prefix_end):
			s_value = schema[num]
			new_path = f'{path}[{num}]'
			if data is None or num >= len(data):
				_format_data(None, s_value, p_line, p_col, p_line, p_col, path=new_path)
			else:
				data[num] = _format_data(data[num], s_value, *data.lc.item(num), *data.lc.item(num), path=new_path)
		# apply repeat to data items at the marker's index and beyond
		if repeat_idx is not None and data is not None:
			rep_schema = schema[repeat_idx].schema
			for num in range(repeat_idx, len(data)):
				new_path = f'{path}[{num}]'
				data[num] = _format_data(data[num], rep_schema, *data.lc.item(num), *data.lc.item(num), path=new_path)

	# bare repeat instance behaves like a single-element sequence schema: list of `schema.schema`
	elif isinstance(schema, repeat):
		if not isinstance(data, MutableSequence) and data is not None:
			raise StructureError(False, data, line, col)
		if data is None and schema.coerce:
			data = []
		if data is not None:
			for num in range(len(data)):
				new_path = f'{path}[{num}]'
				data[num] = _format_data(data[num], schema.schema, *data.lc.item(num), *data.lc.item(num), path=new_path)

	# format the value
	elif isinstance(schema, (required, strict, coerce)):
		return schema(data, line, col, path=path)
	elif callable(schema) and data is not None:
		try:
			return schema(data)
		except TypeError as e:
			raise ConversionTypeError(schema, data, line, col) from e
		except ValueError as e:
			raise ConversionValueError(schema, data, line, col) from e
	return data
