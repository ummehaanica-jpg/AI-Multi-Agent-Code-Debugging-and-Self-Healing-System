from agents.fixer import fix_code

code = '''text = "hello"
result = text.append(" world")
print(result)
'''

result = fix_code(
    code,
    error_type="AttributeError",
    error_msg="'str' object has no attribute 'append'",
)

print("Repair strategy:", result.get("strategy"))
print("Repair description:", result.get("description"))
print("\nProposed code:\n")
print(result.get("fixed_code"))
