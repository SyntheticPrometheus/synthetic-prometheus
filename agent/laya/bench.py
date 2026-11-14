import time, os, resource, json, laya
t0=time.time(); r=laya.Router(max_loaded=1, device="cpu"); print("router %.1fs"%(time.time()-t0))
Q={"department":{"type":"choice","instructions":"Which department should handle this?",
   "criteria":{"billing":"invoices, payments, refunds","technical":"bugs, outages, system errors","other":"everything else"}},
   "urgency":{"type":"score","instructions":"How urgent is this?","criteria":["not urgent","soon","blocking"]}}
text="Hi, we were billed twice for March. Please refund the duplicate today or we will cancel our plan."
t0=time.time(); out=r.predict(text,Q); print("1st predict (incl load) %.2fs"%(time.time()-t0))
for n in (1,5):
    t0=time.time()
    for _ in range(n): out=r.predict(text,Q)
    d=time.time()-t0
    print("%d predicts: %.2fs total, %.2fs/call"%(n,d,d/n))
print(json.dumps(out["answers"],indent=1)[:500])
print("peak RSS MB %.0f"%(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024))
