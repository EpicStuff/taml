import ast, builtins
from collections.abc import Callable, MutableMapping, Mapping, MutableSequence, Sequence
import contextlib
from typing import Any

from epicstuff import Dict, wrap, rmap
from zope.dottedname.resolve import resolve as zresolve


class schema: ...
class required(schema):
	'Indicates value is required.'

	def __init__(self, func: Callable) -> None:
		self.func = func
class strict(schema):
	'Checks if value type is correct instead of converting.'

	def __init__(self, func: Callable) -> None:
		self.func = func

class tmp_error(Exception):
	pass


def _format_data(data: Any, schema: Any) -> Any:
	# if the schema value is a dict
	if isinstance(schema, Mapping):
		# data value has to be a dict or none
		if not isinstance(data, MutableMapping) and data is not None:
			raise Exception('tmp, data needs to be dict or none')
		# go through each item in schema, and run format on it and matching data value
		for s_key, s_value in schema.items():
			# if key does not exist in data, pass None to format function
			if data is None or s_key not in data:
				_format_data(None, s_value)
			else:
				data[s_key] = _format_data(data.get(s_key), s_value)
	# if the schema value is list
	elif isinstance(schema, Sequence):
		# data value has to be a list or none
		if not isinstance(data, MutableSequence) and data is not None:
			raise Exception('tmp, data needs to be list or none')
		# go through each item in schema, and run format on it and each item in data
		for num, s_value in enumerate(schema):
			# if index does not exist in data, pass None to format function
			formated = _format_data(None if data is None or num >= len(data) else data[num], s_value)
			if data is not None and num < len(data):
				data[num] = formated
	# deal with special taml functions
	elif schema == required or isinstance(schema, required):
		if data is None:
			raise tmp_error('tmp, value is required')
		return schema.func(data)
	elif isinstance(schema, strict):
		tmp = schema.func
		if isinstance(schema.func, required):
			if data is None:
				raise tmp_error('tmp, value is required')
			tmp = tmp.func
		if data is not None and not isinstance(data, tmp):
			raise tmp_error(f'tmp, wrong type')
		return data
	# format the value
	elif callable(schema) and data is not None:
		return schema(data)
	return data

def _format_schema(schema: Any) -> Any:
	'Call resolve if value is str.'
	if isinstance(schema, str):
		return _resolve(schema)
	return schema
def _resolve(src: str) -> Any:
	'Converts a string like epicstuff.Dict to a Dict object.'
	def node_to_value(src: str, node: ast.AST) -> Any:
		# convert if is numbers, strings, bools, and None
		if isinstance(node, ast.Constant):
			return node.value
		# convert if is literals (lists, dicts, etc.)
		with contextlib.suppress(Exception):
			return ast.literal_eval(node)

		# else, convert the node to string
		seg = ast.get_source_segment(src, node) or ast.unparse(node)
		# make sure is not stuff like 1 + 2 (ast.BinOp), a if cond else b (ast.IfExp), etc.
		if isinstance(node, (ast.Name, ast.Attribute, ast.Call)):
			return _resolve(seg)
		raise ValueError(f'Unsupported expression in schema args: {seg}')
	resolved_args = []
	resolved_kwargs = {}

	src = src.strip()
	parsed = ast.parse(src, mode='eval').body

	# resolve args first
	## if is callable (eg. func(args), func with brackets)
	if isinstance(parsed, ast.Call):
		# get func as string
		func = ast.get_source_segment(src, parsed.func) or ast.unparse(parsed.func)
		# get each arg and kwarg
		for arg in parsed.args:
			resolved_args.append(node_to_value(src, arg))
		for kwarg in parsed.keywords:
			# reject unpacking
			if kwarg.arg is None:
				raise ValueError('Keyword args must be written as name=value, not **kwargs')
			resolved_kwargs[kwarg.arg] = node_to_value(src, kwarg.value)
	## else, just a func without brackets, like int or epicstuff.Dict
	else:
		func = src

	# resolve func
	## try builtins first
	if hasattr(builtins, func):
		func = getattr(builtins, func)
		return wrap(func, *resolved_args, **resolved_kwargs) if resolved_args or resolved_kwargs else func
	## resolve if not builtin with zope
	func = zresolve(func)
	if func in (required, strict) and (resolved_args or resolved_kwargs):
		# if is strict and theres required (with no brackets)
		if func == strict and (required in resolved_args or required in resolved_kwargs):
			raise Exception("tmp, strict's requried must have arguments")
		# else
		return func(*resolved_args, **resolved_kwargs)
	if func == strict:
		raise Exception('tmp, strict must have arguments')
	return wrap(func, *resolved_args, **resolved_kwargs) if resolved_args or resolved_kwargs else func
