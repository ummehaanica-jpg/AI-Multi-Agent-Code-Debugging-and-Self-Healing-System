from core.orchestrator import run_pipeline

code = '''text = "hello"
result = text.append(" world")
print(result)'''

state = run_pipeline(code, use_llm=False)

for name, value in vars(state).items():
    if any(word in name.lower() for word in (
        "detect", "error", "repair", "status", "log", "attempt"
    )):
        print(f"\n{name} = {value}")
