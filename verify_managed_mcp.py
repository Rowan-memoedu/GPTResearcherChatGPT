"""Opt-in real research/report acceptance, including service idle retirement."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path('D:/Quarantine/MCPorterGPTAcceptance')
NODE = 'C:/Program Files/nodejs/node.exe'
CLI = 'D:/Applications/MCPorter/node_modules/mcporter/dist/cli.js'
CONFIG = ROOT / 'mcporter.json'
NAMESPACE = ROOT / 'namespace'
ENV = {**os.environ, 'MCPORTER_DAEMON_DIR': str(NAMESPACE)}
PORT = 19784

def value(result):
    if result.isError:
        raise RuntimeError(str(result.content))
    answer = result.structuredContent or json.loads(result.content[0].text)
    if answer.get('status') == 'error':
        raise RuntimeError(answer['message'])
    return answer

@asynccontextmanager
async def client():
    async with httpx.AsyncClient(timeout=httpx.Timeout(1900, read=1900), trust_env=False) as http:
        async with streamable_http_client(f'http://127.0.0.1:{PORT}/mcp/gpt-researcher', http_client=http) as (r,w,_):
            async with ClientSession(r,w,read_timeout_seconds=timedelta(minutes=31)) as session:
                await session.initialize()
                yield session

def status():
    result = subprocess.run([NODE,CLI,'--config',str(CONFIG),'daemon','status','--json'],
                            env=ENV,capture_output=True,text=True,check=True)
    return json.loads(result.stdout)

async def check():
    async with client() as first:
        names = [t.name for t in (await first.list_tools()).tools]
        assert {'deep_research','write_report','get_research_context','chatgpt_plan_status'} <= set(names)
        research = value(await first.call_tool('deep_research', {'query':
            'Python with statement file closure on exceptions site:docs.python.org'}))
        assert research.get('source_count', 0) > 0
        research_id = research['research_id']
        original = value(await first.call_tool('get_research_context', {'research_id': research_id}))
        print(f'PASS real research completed with {research["source_count"]} sources; ID saved', flush=True)
    # Windows verifies the whole owned process tree after the idle deadline.
    await asyncio.sleep(40)
    idle = status()
    assert not any(s.get('connected') for s in idle['servers']), 'Research backend did not retire'
    async with client() as resumed:
        restored = value(await resumed.call_tool('get_research_context', {'research_id': research_id}))
        assert restored == original, 'Research context changed after process retirement'
        print('PASS old research ID restored with identical context after idle retirement', flush=True)
        report = value(await resumed.call_tool('write_report', {'research_id':research_id,
            'custom_prompt':'用简体中文写约400字，说明 with 如何在正常结束和异常时关闭文件，保留来源链接。'}))
        assert len(report.get('report','')) > 200 and 'http' in report['report']
        route = value(await resumed.call_tool('chatgpt_plan_status', {}))
        assert route['completed_model_requests'] > 0 and route['session']['sharing']
        print('PASS restored research generated a sourced report through ChatGPT plan', flush=True)
    receipt = {'complete':True, 'tool_names':names, 'research_id':research_id,
               'source_count':research['source_count'], 'context_equal_after_idle':True,
               'report_chars':len(report['report']), 'idle_status':idle,
               'completed_model_requests_after_restart':route['completed_model_requests']}
    Path('D:/Artifacts/DeveloperGovernance/mcp/gpt-recovery-acceptance.json').write_text(
        json.dumps(receipt,indent=2),encoding='utf-8')

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    CONFIG.write_text(json.dumps({'imports':[],'mcpServers':{'gpt-researcher':{
        'command':'D:/Applications/GPTResearcher/venv/Scripts/python.exe',
        'args':['-u','D:/Projects/GPTResearcherChatGPT/app.py','mcp'],
        'env':{'GPTR_MCP_STATE':str(ROOT/'mcp-state.sqlite3'),'GPTR_NODE':NODE},
        'lifecycle':{'mode':'keep-alive','idleTimeoutMs':3000}}}},indent=2),encoding='utf-8')
    log=(ROOT/'bridge.log').open('w',encoding='utf-8')
    bridge=subprocess.Popen([NODE,'D:/Projects/DeveloperGovernance/mcp-bridge.mjs',str(CONFIG),str(NAMESPACE),str(PORT)],
        stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(100):
            if bridge.poll() is not None: raise RuntimeError('Bridge exited')
            try:
                with socket.create_connection(('127.0.0.1',PORT),timeout=.1): break
            except OSError: time.sleep(.1)
        else: raise RuntimeError('Bridge did not listen')
        asyncio.run(check())
    finally:
        stop=subprocess.run([NODE,CLI,'--config',str(CONFIG),'daemon','stop'],env=ENV,capture_output=True,text=True,timeout=90)
        print(f'Test daemon stop exit={stop.returncode}',flush=True)
        if stop.returncode: print(stop.stderr[-600:],flush=True)
        bridge.terminate()
        bridge.wait(timeout=15)
        log.close()

if __name__=='__main__': main()
