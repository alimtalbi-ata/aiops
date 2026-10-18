from fastapi import FastAPI
app = FastAPI(title="AioOps Integration", version="2.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "component": "integration", "mode": "adapter-ready"}

@app.get("/api/adapters")
def adapters():
    return {"adapters": [], "status": "NOT_CONFIGURED"}
