import contextlib, re, tempfile, unittest
from collections.abc import Callable, Generator
from functools import wraps
from pathlib import Path
from typing import Any, Literal, ParamSpec

from epicstuff import NewDict, run_fix_import, s  # noqa: F401
from taml import taml


# functions used by tests
skipped_tests: list[tuple[str, str]] = []
P = ParamSpec('P')
def skip(reason: str) -> Callable[[Callable[P, None]], Callable[P, None]]:
	'Skip in Green, actually skip during direct `.debug()` runs.'
	def decorator(func: Callable[P, None]) -> Callable[P, None]:
		if func.__module__ != '__main__':
			return unittest.skip(reason)(func)

		@wraps(func)
		def skipped(*_a: P.args, **_k: P.kwargs) -> None:
			if (func.__name__, reason) not in skipped_tests:
				if not skipped_tests:
					print('Skipped tests:')
				skipped_tests.append((func.__name__, reason))
				print(f'\t{func.__name__}: {reason}')
		return skipped
	return decorator

@contextlib.contextmanager
def create_file(text: str, name: str = 'test.taml') -> Generator[Path]:
	'Create a temporary text file and remove it after the test.'
	with tempfile.TemporaryDirectory() as tmp_dir:
		path = Path(tmp_dir) / name
		path.write_text(text)
		yield path

def assert_equals(schema: str, native: Any, data: str, expected: Any) -> None:  # pyright: ignore[reportRedeclaration]
	'Test schema parsing, then data parsing with both native and parsed schema.'
	schema: NewDict = taml.loads(schema, is_schema=True)
	assert schema == native
	assert taml.loads(data, schema) == expected
	assert taml.loads(data, native) == expected
def assert_raises2(schema: str, native: dict, data: str, expected: type[Exception], msg: str | None = None) -> None:  # pyright: ignore[reportRedeclaration]
	'Parse schema text and assert it equals native, then drive data through both the parsed schema and the native schema, expecting the same result (or, if expected is an exception type, the same error).'
	schema: NewDict = taml.loads(schema, is_schema=True)
	assert schema == native
	assert_raises(expected, lambda: taml.loads(data, schema), msg)
	assert_raises(expected, lambda: taml.loads(data, native), msg)
def assert_raises(exc_type: type[BaseException] | tuple[type[BaseException], ...], fn: Callable, msg: str | None = None, strict: bool = True) -> None:
	try:
		fn()
	except exc_type as e:
		if msg is None:
			return

		actual = str(e)
		if actual == msg:
			return

		if not strict:
			location_pattern = r'(?s)^(.*) \(line \d+, col \d+\)$'
			expected_match = re.fullmatch(location_pattern, msg)
			actual_match = re.fullmatch(location_pattern, actual)

			if expected_match is not None and actual_match is not None and expected_match.group(1) == actual_match.group(1):
				print(s(f'''
					Exception location mismatch:
						Expected: {msg}
						Actual:   {actual}
				'''))
				return

		raise AssertionError(s(f'''
			Exception message mismatch:
				Expected: {msg}
				Actual:   {actual}
		''')).with_traceback(e.__traceback__) from e
	name = (
		' | '.join(error.__name__ for error in exc_type)
		if isinstance(exc_type, tuple)
		else exc_type.__name__
	)
	raise AssertionError(f'Expected {name} to be raised')

# functions used in test schemas
recorded_values: list[Any] = []
def record_value(value: Any, a: Any = None) -> Any:
	recorded_values.append((value, a))
	return value

def return_none(_: Any) -> None:
	return None
def return_value(_: Any) -> Literal['test']:
	return 'test'
def raise_runtime_error(_value: Any) -> None:
	raise RuntimeError('runtime failure')
