from fastapi import FastAPI
app=FastAPI(title='AIOps2 Evidence',version='8.0.0')
@app.get('/health')
def health(): return {'status':'ok','service':'evidence','version':'8.0.0','port':812}
