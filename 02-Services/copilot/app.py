from fastapi import FastAPI
app=FastAPI(title='AIOps2 Copilot',version='8.0.0')
@app.get('/health')
def health(): return {'status':'ok','service':'copilot','version':'8.0.0','port':814}
