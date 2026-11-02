from agents.fixer import fix_code

code = """student_name = "Haani"
print(student_nme)"""

error_msg = "name 'student_nme' is not defined. Did you mean: 'student_name'?"

result = fix_code(
    code,
    "NameError",
    error_msg
)

print("\n--- ORIGINAL CODE ---")
print(code)

print("\n--- FIXED CODE ---")
print(result)