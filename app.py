"""Launch GPT Researcher with official ChatGPT plan inference and isolated data."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime


def configure():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    root = Path(os.getenv("GPTR_DATA", "D:/AppData/GPTResearcher"))
    cache = Path(os.getenv("GPTR_CACHE", "D:/Caches/GPTResearcher"))
    work = root / "work"
    work.mkdir(parents=True, exist_ok=True)
    os.chdir(work)
    for variable, path in {"HF_HOME": cache / "huggingface", "NLTK_DATA": cache / "nltk", "PIP_CACHE_DIR": cache / "pip", "TEMP": cache / "tmp", "TMP": cache / "tmp"}.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[variable] = str(path)
    # This launcher cannot fall back to separately billed model APIs or send tracing payloads.
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORGANIZATION", "OPENAI_PROJECT", "LANGCHAIN_API_KEY", "LANGSMITH_API_KEY", "TYPESAFE_API_KEY", "LLM_KWARGS"):
        os.environ.pop(name, None)
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["MONOCLE_TRACING"] = "false"
    os.environ["ALLOW_PRIVATE_URLS"] = "false"
    configuration = root / "research-config.json"
    os.environ["CONFIG_PATH"] = str(configuration)
    config = json.loads(configuration.read_text(encoding="utf-8"))
    # Clear inherited per-field overrides before selecting this app's configuration.
    for name in config:
        os.environ.pop(name, None)
    return root


async def research(args):
    from gpt_researcher import GPTResearcher
    from plan_provider import bridge
    target = Path(args.output) if args.output else Path("D:/Artifacts/GPTResearcher/reports") / f"report-{datetime.now():%Y%m%d-%H%M%S}.md"
    if target.exists() or target.with_suffix(".receipt.json").exists():
        raise FileExistsError("Choose a new report path; existing reports are preserved")
    researcher = GPTResearcher(
        query=args.query, report_type="deep" if args.deep else "research_report",
        source_urls=args.source_url or None,
        complement_source_urls=not bool(args.source_url), verbose=False,
    )
    with contextlib.redirect_stdout(sys.stderr):
        await researcher.conduct_research()
        report = await researcher.write_report()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        handle.write(report)
    receipt = {
        "report": str(target), "report_chars": len(report),
        "sources": researcher.get_source_urls(),
        "research_source_count": len(researcher.get_research_sources()),
        "completed_model_requests": bridge.completed_requests,
        "model_billing": "chatgpt-plan", "search": "duckduckgo",
    }
    target.with_suffix(".receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    if len(report) < 200 or not receipt["sources"] or not bridge.completed_requests:
        raise RuntimeError("Research did not produce a sourced report")


def mcp_server():
    vendor = Path(os.getenv("GPTR_RUNTIME", "D:/Applications/GPTResearcher")) / "mcp"
    sys.path.insert(0, str(vendor))
    with contextlib.redirect_stdout(sys.stderr):
        import server
    original = server.GPTResearcher
    operation_lock = asyncio.Lock()

    class QuietResearcher(original):
        async def conduct_research(self, *args, **kwargs):
            async with operation_lock:
                with contextlib.redirect_stdout(sys.stderr):
                    return await super().conduct_research(*args, **kwargs)

        async def write_report(self, *args, **kwargs):
            async with operation_lock:
                with contextlib.redirect_stdout(sys.stderr):
                    report = await super().write_report(*args, **kwargs)
                if hasattr(self, "_mcp_research_id"):
                    server.mcp.researchers[self._mcp_research_id] = self
                return report

        async def quick_search(self, *args, **kwargs):
            async with operation_lock:
                with contextlib.redirect_stdout(sys.stderr):
                    return await super().quick_search(*args, **kwargs)

    server.GPTResearcher = QuietResearcher
    from mcp_state import DurableResearchers, JsonStore
    from gpt_researcher.utils.enum import Tone
    import utils

    def restore_researcher(**kwargs):
        kwargs["tone"] = Tone(kwargs["tone"])
        return QuietResearcher(**kwargs)

    state_path = Path(os.getenv("GPTR_MCP_STATE", str(
        Path(os.getenv("GPTR_DATA", "D:/AppData/GPTResearcher")) / "mcp-state.sqlite3")))
    server.mcp.researchers = DurableResearchers(state_path, restore_researcher)
    utils.research_store = server.research_store = JsonStore(state_path, "topics")

    @server.mcp.tool()
    async def chatgpt_plan_status() -> dict:
        """Read the local ChatGPT plan connection and completed inference count; never return credentials."""
        from plan_provider import bridge
        async with operation_lock:
            session = await asyncio.to_thread(bridge.call, "status")
        return {"session": session, "billing_route": "official-chatgpt-plan",
                "completed_model_requests": bridge.completed_requests}

    # Reuse upstream tools, while bypassing its API-key-only launcher and stdout banner.
    server.mcp.run(transport="stdio", show_banner=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["status", "probe", "research", "mcp"])
    parser.add_argument("--query")
    parser.add_argument("--source-url", action="append", default=[])
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    configure()
    with contextlib.redirect_stdout(sys.stderr):
        from plan_provider import bridge, install_provider
        install_provider()
        from proxy_dns import install_proxy_dns_validation
        install_proxy_dns_validation()
    if args.mode == "mcp":
        mcp_server()
    elif args.mode == "status":
        print(json.dumps({"session": bridge.call("status"), "models": bridge.call("models")}, ensure_ascii=False))
    elif args.mode == "probe":
        from gpt_researcher.utils.llm import create_chat_completion
        result = asyncio.run(create_chat_completion(
            messages=[{"role": "system", "content": "Follow the user's exact output request."},
                      {"role": "user", "content": "Reply with exactly: GPT Researcher integration works."}],
            model="gpt-6.1-sol", llm_provider="openai", stream=False))
        print(json.dumps({"response": result, "completed_model_requests": bridge.completed_requests}, ensure_ascii=False))
        if result.strip() != "GPT Researcher integration works.":
            raise RuntimeError("Unexpected integration probe response")
    else:
        if not args.query:
            parser.error("--query is required for research")
        asyncio.run(research(args))


if __name__ == "__main__":
    main()
