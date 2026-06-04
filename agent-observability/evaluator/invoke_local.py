"""Locally simulate a Lambda invocation of the evaluator with a hardcoded event.

Run from within the evaluator/ directory:

    python invoke_local.py
"""
import json

from handler import lambda_handler

TEST_EVENT = {
    "trace_id": "demo-trace-0001",
    "input": "What is the capital of France?",
    "output": "The capital of France is Paris.",
}


def main():
    result = lambda_handler(TEST_EVENT, context=None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
