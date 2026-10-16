import os


# Keep the test suite deterministic and avoid depending on an external LLM.
os.environ["LLM_PROVIDER"] = "rules"
os.environ["LLM_ENABLED"] = "false"
