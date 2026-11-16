import asyncio, json, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ENV={"LAYA_DEVICE":"cpu","LAYA_MODELS":"english","LAYA_THREADS":"4","LAYA_PRELOAD":"1","MKL_ENABLE_INSTRUCTIONS":"SSE4_2","PATH":"/usr/bin:/bin","HOME":"$HOME"}
Q={"department":{"type":"choice","instructions":"Which department should handle this?",
     "criteria":{"billing":"invoices, payments, refunds","technical":"bugs, outages, system errors","other":"everything else"}},
   "urgency":{"type":"score","instructions":"How urgent is this?","criteria":["not urgent","soon","blocking"]},
   "churn":{"type":"noul","instructions":"Does the customer threaten to cancel?",
            "labels":{"true":"A","false":"B"}}}
async def main():
    async with stdio_client(StdioServerParameters(command=".venv/bin/laya-mcp-server",args=[],env=ENV)) as (r,w):
        async with ClientSession(r,w) as s:
            t0=time.time(); await s.initialize(); print("init %.2fs"%(time.time()-t0))
            for txt in ["Hi, we were billed twice for March. Please refund the duplicate today or we will cancel our plan.",
                        "Server 500s on /api/checkout since the 14:02 deploy. Whole checkout is down, customers complaining."]:
                for i in range(2):
                    t0=time.time(); res=await s.call_tool("laya_predict",{"state":{"request":txt},"questions":Q}); d=time.time()-t0
                    o=json.loads(res.content[0].text)
                    a=o.get("answers",o)
                    print("%.2fs" % d, {k:(v.get("choice") or round(v.get("score",v.get("noul",0)),2), v.get("confidence")) for k,v in a.items() if isinstance(v,dict)}, "| route", o.get("routing",{}).get("model"))
asyncio.run(main())
