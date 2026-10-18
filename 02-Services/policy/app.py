from fastapi import FastAPI
app=FastAPI(title='AIOps2 Policy',version='8.0.0')
@app.get('/health')
def health(): return {'status':'ok','service':'policy','version':'8.0.0','port':813}
