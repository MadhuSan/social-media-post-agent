"""
Diagnostic script - run from project root to reproduce the 502 error.
Safe: does a real graph.invoke with a fake social_account_id so it will
fail at the DB lookup, giving us the full traceback without side-effects.
"""
import sys, traceback

print("=== Step 1: imports ===")
try:
    from agent import graph
    from prompts.birdsPrompt import system_prompt, user_prompt
    print("  OK")
except Exception:
    print("  FAILED:")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 2: model smoke-test (one token) ===")
try:
    from models import model
    resp = model.invoke([{"role": "user", "content": "Say only the word HELLO."}])
    print(f"  content repr: {repr(resp.content[:120])}")
    print(f"  tool_calls: {getattr(resp, 'tool_calls', None)}")
except Exception:
    print("  FAILED:")
    traceback.print_exc()

print("\n=== Step 3: graph.invoke (fake social_account_id) ===")
try:
    result = graph.invoke(
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "search_query": "BIRDS clinic respiratory Bangalore",
            "social_account_id": "00000000-0000-0000-0000-000000000000",
        }
    )
    print("  result keys:", list(result.keys()))
    print("  draft_result:", result.get("draft_result"))
    generated = result.get("generated_content", "")
    print(f"  generated_content length: {len(generated)}")
    print(f"  generated_content preview: {repr(generated[:200])}")
except Exception:
    print("  FAILED:")
    traceback.print_exc()
