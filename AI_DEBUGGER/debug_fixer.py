from agents.error_detector import detect_errors
from agents.fixer import fix_code
from pathlib import Path


files = [
    "dataset/typeerror/typeerror_01.py",
    "dataset/attributeerror/attributeerror_01.py",
    "dataset/indexerror/indexerror_02.py",
    "dataset/runtime/runtime_01.py",
    "dataset/syntax/syntax_03.py",
]


for file in files:
    print("\n" + "=" * 60)
    print(file)
    print("=" * 60)

    code = Path(file).read_text(encoding="utf-8")

    detection = detect_errors(code)

    print("\nDETECTION:")
    print(detection)

    error_type = detection.get("error_type", "")
    error_message = detection.get("error_msg", "")

    print("\nERROR TYPE:", repr(error_type))
    print("ERROR MESSAGE:", repr(error_message))

    result = fix_code(code, error_type, error_message)

    print("\nFIX RESULT:")
    print(result)