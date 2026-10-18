from fastapi import FastAPI
app=FastAPI(title='AIOps2 Rag',version='8.0.0')
@app.get('/health')
def health(): return {'status':'ok','service':'rag','version':'8.0.0','port':819}
