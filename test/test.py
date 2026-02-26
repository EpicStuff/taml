import datetime
from taml import taml
from epicstuff import Dict

print(taml.default_flow_style)

tmp = {
	'a': {
		'd': tuple
	}
}
out = taml.load(r'C:\Users\dqi\Documents\Projects\taml\test\test.taml', r'C:\Users\dqi\Documents\Projects\taml\test\schema_test.taml', tmp)
assert out == Dict({'a': Dict({'a': 3, 'b': datetime.datetime(2000, 4, 24, 12, 36, 16, tzinfo=datetime.timezone.utc), 'c': (1, 2, 3), 'd': (1.12, 2, Dict({'a': 1, 'b': '1'}), '4')})})
print(out)
