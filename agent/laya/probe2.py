import asyncio, json, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ENV={"LAYA_DEVICE":"cpu","LAYA_MODELS":"english","LAYA_THREADS":"4","LAYA_PRELOAD":"1","PATH":"/usr/bin:/bin","HOME":"$HOME"}
SCHEMA={"type":"object","properties":{
  "priority":{"type":"string","enum":["low","normal","urgent"]},
  "needs_human":{"type":"boolean"},
  "severity":{"type":"integer","minimum":1,"maximum":5}},"required":["priority"]}
STATES=[{"request":t} for t in [
 "Prod database is down, all writes failing since 10 minutes ago.",
 "Can you add dark mode to the settings page? No rush.",
 "Invoice INV-2231 shows the wrong VAT rate, please correct it.",
 "Someone posted our internal roadmap on a public forum.",
]]
Q={"priority":{"type":"choice","instructions":"How urgent is this request?","criteria":{"low":"nice to have, no deadline","normal":"should be done this week","urgent":"production impact or deadline today"}}}
async def main():
    async with stdio_client(StdioServerParameters(command=".venv/bin/laya-mcp-server",args=[],env=ENV)) as (r,w):
        async with ClientSession(r,w) as s:
            await s.initialize()
            t0=time.time(); r1=await s.call_tool("laya_decide",{"state":STATES[1],"schema":SCHEMA}); print("decide %.2fs"%(time.time()-t0))
            print(r1.content[0].text[:600])
            t0=time.time(); r2=await s.call_tool("laya_predict_batch",{"requests":[{"state":st,"questions":Q} for st in STATES]}); print("batch4 %.2fs"%(time.time()-t0))
            print(r2.content[0].text[:400])
asyncio.run(main())
