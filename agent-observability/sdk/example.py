"""Demo: instrument a fake LLM call with the AgentTracer SDK and send a trace.

Run from within the sdk/ directory (so the generated stubs are importable):

    python example.py
"""
import asyncio
import logging

from tracer import AgentTracer

logging.basicConfig(level=logging.INFO)


async def main():
    tracer = AgentTracer(app_name="demo-app", server_host="localhost", server_port=50051)

    # A fake "LLM" function — its input/output/latency are auto-captured by @instrument.
    @tracer.instrument
    async def fake_llm(prompt: str) -> str:
        await asyncio.sleep(0.05)  # simulate model latency
        return f"Echo: {prompt}"

    try:
        answer = await fake_llm("What is agent observability?")
        print("LLM responded:", answer)
    finally:
        await tracer.close()


if __name__ == "__main__":
    asyncio.run(main())
