"""Exercise the installed upstream MCP tools with a bounded public research query."""
import argparse
import asyncio
from datetime import timedelta
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def payload(result):
    if result.isError:
        raise RuntimeError("MCP tool returned an error")
    if result.structuredContent:
        return result.structuredContent
    for content in result.content:
        if content.type == "text":
            return json.loads(content.text)
    raise RuntimeError("MCP tool returned no structured result")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--query", default="Python with statement file closure on exceptions site:docs.python.org")
    args = parser.parse_args()
    output = Path("D:/Artifacts/GPTResearcher/verification")
    output.mkdir(parents=True, exist_ok=True)
    server = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name("app.py")), "mcp"])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(minutes=20)) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            print(json.dumps({"mcp_tools": names}), flush=True)
            required = {"deep_research", "quick_search", "write_report", "get_research_sources", "get_research_context"}
            if not required.issubset(names):
                raise RuntimeError("Expected upstream research tools are missing")
            search = payload(await session.call_tool("quick_search", {"query": "Python context manager with statement official documentation"}))
            (output / "mcp-search.json").write_text(json.dumps(search, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"search_status": search.get("status"), "result_count": search.get("result_count")}), flush=True)
            if search.get("status") != "success" or not search.get("result_count"):
                raise RuntimeError("MCP search returned no results")
            if args.research:
                research = payload(await session.call_tool("deep_research", {"query": args.query}))
                (output / "mcp-research-data.json").write_text(json.dumps(research, ensure_ascii=False, indent=2), encoding="utf-8")
                if research.get("status") != "success" or not research.get("research_id") or not research.get("source_count"):
                    raise RuntimeError("MCP research failed to collect sources")
                report = payload(await session.call_tool("write_report", {"research_id": research["research_id"], "custom_prompt": "用简体中文写约400字，说明 with 如何在正常结束和异常时关闭文件，保留可访问的来源链接。"}))
                text = report.get("report", "")
                if report.get("status") != "success" or len(text) < 200 or "http" not in text:
                    raise RuntimeError("MCP report was empty or lacked citations")
                (output / "mcp-research-report.md").write_text(text, encoding="utf-8")
                route = payload(await session.call_tool("chatgpt_plan_status", {}))
                if not route.get("session", {}).get("sharing") or not route.get("completed_model_requests"):
                    raise RuntimeError("The MCP run did not confirm completed ChatGPT plan inference")
                receipt = {"query": args.query, "mcp_tools": names, "source_count": research["source_count"], "source_urls": research.get("source_urls"), "report_chars": len(text), **route, "complete": True}
                (output / "mcp-research-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
