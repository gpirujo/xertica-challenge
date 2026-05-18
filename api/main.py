from fastapi import FastAPI

app = FastAPI(title="Compliance Agent API", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok"}
