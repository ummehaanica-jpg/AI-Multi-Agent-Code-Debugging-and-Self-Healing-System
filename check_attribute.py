from agents.fixer import _fix_attribute_error

code = '''text = "hello"
result = text.append(" world")
print(result)
'''

fixed = _fix_attribute_error(
    code,
    "'str' object has no attribute 'append'",
)

print("Repaired code:")
print(fixed)
