# GPT Researcher with ChatGPT plan usage

Local integration of GPT Researcher with OpenAI's official Sign in with ChatGPT flow and public Responses API. Authentication, permission checks, token rotation and completed-response handling use the official `@siwc/local` DevKit.

The integration is intended for a single user's Windows machine. Runtime packages, encrypted account state, reports and caches are stored separately from this source repository. No account credentials or research material belong in Git.

The OpenAI authentication and inference probe has succeeded. GPT Researcher installation and end-to-end integration are being configured; installation is complete only after a real GPT Researcher report passes verification.

Upstream references:

- https://github.com/assafelovic/gpt-researcher
- https://github.com/assafelovic/gptr-mcp
- https://github.com/openai/sign-in-with-chatgpt-devkit
- https://developers.openai.com/siwc/token-sharing-open-source
