import ast, builtins, contextlib, sys
from collections.abc import Callable, Mapping, MutableMapping, MutableSequence
from types import TracebackType
from typing import Any, Never, Self

from epicstuff import NewDict as Dict, wrap, _Unset, _unset
from ruamel.yaml import YAMLError
from zope.dottedname.resolve import resolve as zresolve

from .stuff import beartype


type List[a] = tuple[a, ...] | list[a]

class Schema:
	@classmethod
	def from_taml(cls, path: str, line: int, col: int, func: Callable | None | _Unset = _unset, _arg_cols: List[int] = ()) -> Self:
		'Exception messages and Checks for taml str to python conversion.'
		# Make sure that func exists
		if func is _unset and cls is not required:
			raise SchemaDefinitionError(f'Missing arguments for {cls.__name__} at {path} (line {line+1}, col {col+1})')
		if func is _unset:  # for required
			func = None
		# If beartype error, replace with better exception
		try:
			return cls(func, path)
		except TypeError as e:
			raise SchemaDefinitionError(f'{func!r} at {path} is not callable (line {line+1}, col {(_arg_cols[0] if _arg_cols else col)+1})') from e

	# subclasses are expected to overwrite to tighten func typing
	def __init__(self, func: Any, _source: None | str = None) -> None:  # pyright: ignore[reportRedeclaration]
		'Note, do not pass `_source`.'
		# if no line/col / not from taml, get traceback
		if _source is None:
			frame = sys._getframe(1)
			# skip frames inside this module (eg. required/strict __init__) so the traceback points at the caller's definition site
			while frame.f_back is not None and (frame.f_globals.get('__name__') == __name__ or frame.f_code.co_filename.startswith('<@beartype(')):
				frame = frame.f_back
			_source: TracebackType = TracebackType(None, frame, frame.f_lasti, frame.f_lineno)
		self.func: Any = func; self._source: str | TracebackType = _source
	def __call__(self, data: Any, line: int, col: int, _path: str = '') -> Any:
		try:
			return self.func(data)
		except TypeError:
			self._raise(ConversionTypeError, self.func, data, line, col)
		except ValueError:
			self._raise(ConversionValueError, self.func, data, line, col)
		except Exception as e:
			#self._raise(OtherError, line, col)
			e.add_note(f'(line {line+1}, col {col+1})')
			raise
	def _raise(self, execption: type[Exception], *args, **kwargs) -> Never:
		if isinstance(self._source, str):
			raise execption(*args, **kwargs)
		raise execption(*args, **kwargs).with_traceback(self._source)
	def __eq__(self, other: object) -> bool:
		'Compare by concrete type and wrapped func, ignoring _source, so a native schema equals its parsed form.'
		return type(self) is type(other) and self.func == other.func  # pyright: ignore[reportAttributeAccessIssue]
	# todo: maybe do @property source, and call it in required instead of the if
class required(Schema):
	'Indicates value is required.'

	@beartype
	def __init__(self, func: Callable | None = None, _source: None | str = None) -> None:
		super().__init__(func, _source)

	def __call__(self, data: Any, line: int, col: int, _path: str = '') -> Any:
		if data is None or data is _unset:
			# prefer the data path from the current walk; fall back to a parsed path or a generic name
			name = _path or (self._source if isinstance(self._source, str) else 'value')
			if isinstance(self._source, str):
				raise RequiredError(name, line, col)
			raise RequiredError(name, line, col).with_traceback(self._source)
		# a nested Schema (eg. strict) does its own check/call
		if isinstance(self.func, Schema):
			return self.func(data, line, col, _path)
		if self.func is not None:
			return super().__call__(data, line, col, _path)
		return data
class strict(Schema):  # noqa: PLW1641
	'Checks if value type is correct instead of converting.'

	@classmethod
	def from_taml(cls, path: str, line: int, col: int, *funcs: type | Any, _arg_cols: List[int] = ()) -> Self:
		'Make sure that at least one type is given.'
		if not funcs:
			raise SchemaDefinitionError(f'Missing arguments for strict at {path} (line {line+1}, col {col+1})')
		try:
			return cls(*funcs, _source=path)
		except TypeError:
			num, bad = next((num, bad) for num, bad in enumerate(funcs) if not isinstance(bad, type))
			if isinstance(bad, required):
				bad.__name__ = 'required'
			raise SchemaDefinitionError(f'{getattr(bad, '__name__', repr(bad))} at {path} is not a type (line {line+1}, col {_arg_cols[num]+1})') from None
	@beartype
	def __init__(self, func: type, *funcs: type, _source: None | str = None) -> None:
		super().__init__((func, *funcs), _source)
	def __call__(self, data: Any, line: int, col: int, _path: str = '') -> Any:
		if data is not _unset and type(data) not in self.func:
			self._raise(StrictError, self.func, data, line, col)
		return data
	def __eq__(self, other: object) -> bool:
		'super().__eq__ but with looser/special func check.'
		return isinstance(other, Schema) and type(self) is type(other) and set(self.func) == set(other.func)
class always(Schema):
	'''Apply `func` to the value even when it is None.

	Plain callables are skipped on null/missing values so a schema never converts an absent field.
	Wrap the callable in `taml.always` when the converter is supposed to run on null/missing.
	'''

	@beartype
	def __init__(self, func: Callable, _source: None | str = None) -> None:
		super().__init__(func, _source)

	def __call__(self, data: Any, line: int, col: int, _path: str = '') -> Any:
		if data is _unset:
			return data
		return super().__call__(data, line, col, _path)
class repeat(Schema): ...

class SchemaError(YAMLError):
	@classmethod
	def name(cls, value: Callable[..., Any]) -> str:
		if isinstance(value, wrap):
			value = value.func
		return getattr(value, '__name__', type(value).__name__)
class RequiredError(SchemaError, ValueError):
	def __init__(self, path: str, line: int, col: int) -> None:
		assert path, 'look into this'
		super().__init__(f'{path} is required (line {line+1}, col {col+1})')
class StrictError(SchemaError, TypeError):
	def __init__(self, expected: Any, data: Any, line: int, col: int) -> None:
		expected = ' | '.join(e.__name__ for e in tuple(expected))
		super().__init__(f'Expected {expected}, got {data!r} (line {line+1}, col {col+1})')
class StructureError(SchemaError, TypeError):
	def __init__(self, mapping: bool, data: Any, line: int, col: int) -> None:
		t = 'dict' if mapping else 'list'
		super().__init__(f'Expected {t} or None, got {data!r} (line {line+1}, col {col+1})')
class SchemaDefinitionError(SchemaError, ValueError): ...

class SchemaImportError(SchemaError, ImportError): ...  # pyright: ignore[reportUnsafeMultipleInheritance, reportIncompatibleVariableOverride]
class ConversionTypeError(SchemaError, TypeError):
	def __init__(self, schema: Callable, data: Any, line: int, col: int) -> None:
		super().__init__(f'Cannot convert {data!r} to {self.name(schema)} (line {line+1}, col {col+1})')
class ConversionValueError(SchemaError, ValueError):
	def __init__(self, schema: Callable, data: Any, line: int, col: int) -> None:
		super().__init__(f'Cannot convert {data!r} to {self.name(schema)} (line {line+1}, col {col+1})')
#class OtherError(SchemaError):
#	def __init__(self, line: int, col: int) -> None:
#		super().__init__(f'Some other error occurred (line {line+1}, col {col+1})')

def _format_schema(schema: Dict | Any, line: int | None = None, col: int | None = None, path: str = '') -> Any | None:
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
		return _resolve(schema, line or 0, col or 0, path.lstrip('.'))
	# make sure is callable so error on schema definition instead of conversion, (containers are handled above)
	if not isinstance(schema, (MutableSequence, MutableMapping)) and not callable(schema):
		raise SchemaDefinitionError(f'{schema!r} at {path.lstrip('.')} is not callable (line {(line or 0)+1}, col {(col or 0)+1})')
	# else
	return schema
def _resolve(src: str, line: int, col: int, path: str, is_arg: bool = False) -> Any:
	'Convert strings like epicstuff.Dict to a Dict object.'
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
			return _resolve(seg, line, col + node.col_offset, path, True)
		assert hasattr(node, 'col_offset'), 'look into this'
		raise SchemaDefinitionError(f'Unsupported expression {seg!r} at {path} (line {line+1}, col {col + node.col_offset+1})')  # pyright: ignore[reportAttributeAccessIssue]
	resolved_args = []
	resolved_kwargs = {}
	arg_cols = []  # column of each positional arg, so schema objects can report on a specific argument

	src = src.strip()
	parsed = ast.parse(src, mode='eval').body

	# resolve args first
	## if is callable (eg. func(args), func with brackets)
	if isinstance(parsed, ast.Call):
		# get func as string
		func = ast.get_source_segment(src, parsed.func) #or ast.unparse(parsed.func)
		assert func is not None, 'tmp, look into this, maybe reenable the o ast...'
		# get each arg
		resolved_args.extend(node_to_value(src, arg) for arg in parsed.args)
		arg_cols.extend(col + arg.col_offset for arg in parsed.args)
		# get each kwarg
		for kwarg in parsed.keywords:
			# reject unpacking
			if kwarg.arg is None:
				raise SchemaDefinitionError(f'Keyword argument must be written as name=value at {path} (line {line + 1}, col {col + kwarg.col_offset + 1})')
			if kwarg.arg in resolved_kwargs:
				raise SyntaxError(f'keyword argument repeated: {kwarg.arg}')
			resolved_kwargs[kwarg.arg] = node_to_value(src, kwarg.value)
	## else, just a func without brackets, like int or epicstuff.Dict
	else:
		func = src

	# resolve func
	name = func  # keep the source name for error messages
	## try builtins first
	if hasattr(builtins, func):
		func = getattr(builtins, func)
	## resolve if not builtin
	else:
		try:
			func = zresolve(func)
		except ImportError as e:
			raise SchemaImportError(f'{e} at {path} (line {line+1}, col {col+1})') from e  # todo: maybe replace {e} with {name}
		## if its a special schema object
		if isinstance(func, type) and issubclass(func, Schema):
			return func.from_taml(path, line, col, *resolved_args, _arg_cols=arg_cols, **resolved_kwargs)
	## schema only supports callables, raise error on definition instead of when formating data
	if not is_arg and not callable(func):
		raise SchemaDefinitionError(f'{name} at {path} is not callable (line {line+1}, col {col+1})')
	## wrap func with args
	return wrap(func, *resolved_args, **resolved_kwargs) if resolved_args or resolved_kwargs else func

def _format_data(data: Any, schema: Any, lc: tuple[int, int] = (0, 0), plc: tuple[int, int] | None = None, path: str = '') -> Any:  # lc = line/col, plc = parent line/col
	plc = plc or lc
	# if the schema value is a dict
	if isinstance(schema, Mapping):
		# data value has to be a dict or none
		if not (isinstance(data, MutableMapping) or data is None or data is _unset):  # TODO: with the introduction of unset, consider if None should still be accepted
			raise StructureError(True, data, *lc)
		# go through each item in schema, and run format on it and matching data value
		has_lc = hasattr(data, 'lc')  # data from an earlier schema conversion (eg. json.loads) has no line/col info, fall back to this structure's location
		for s_key, s_value in schema.items():  # schema key, schema value
			# if key does not exist in data, pass None and parent key line/col to self
			if data is None or data is _unset or s_key not in data:
				_format_data(_unset, s_value, plc, path=f'{path}.{s_key}')
			else:
				data[s_key] = _format_data(data.get(s_key), s_value, data.lc.value(s_key) if has_lc else lc, data.lc.key(s_key) if has_lc else plc, f'{path}.{s_key}')
	# if the schema value is list
	elif isinstance(schema, (list | tuple | set | frozenset)):
		# data value has to be a list or none
		if not (isinstance(data, MutableSequence) or data is None or data is _unset):
			raise StructureError(False, data, *lc)
		# go through each item in schema, and run format on it and each item in data
		has_lc = hasattr(data, 'lc')  # mappings from an earlier schema conversion has no line/col info, fall back to this structure's location
		for num, s_value in enumerate(schema):
			# if index does not exist in data, pass None and parent key line/col to self
			if data is None or data is _unset or num >= len(data):
				_format_data(_unset, s_value, plc, path=f'{path}[{num}]')
			else:
				data[num] = _format_data(data[num], s_value, data.lc.item(num) if has_lc else lc, path=f'{path}[{num}]')

	# format the value
	elif isinstance(schema, (required, strict, always)):
		return schema(data, *lc, path.lstrip('.'))
	elif callable(schema) and data is not None and data is not _unset:
		try:
			return schema(data)
		except TypeError as e:
			raise ConversionTypeError(schema, data, *lc) from e
		except ValueError as e:
			raise ConversionValueError(schema, data, *lc) from e
	else:
		assert data is None or data is _unset, 'tmp, look into this (schema should always be a callable at this point i think)'
	return data
