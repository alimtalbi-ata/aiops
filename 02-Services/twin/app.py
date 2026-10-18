from fastapi import FastAPI
app=FastAPI(title='AIOps2 Twin',version='8.0.0')
@app.get('/health')
def health(): return {'status':'ok','service':'twin','version':'8.0.0','port':811}
