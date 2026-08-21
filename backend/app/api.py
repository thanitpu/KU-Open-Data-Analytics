from io import BytesIO
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from .orchestrator import execute_analysis
from .reporting import build_executive_report

app = FastAPI(title='Automated Analytics Service', version='0.1.0')

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/analyze')
async def analyze(
    file: UploadFile = File(...),
    intent: str = Form(...),
    target: str | None = Form(None),
    mode: str = Form('fast'),
):
    try:
        raw = await file.read()
        df = pd.read_csv(BytesIO(raw))
        result, _ = execute_analysis(
            df=df, intent=intent, target=target, mode=mode
        )
        return {
            'result': result,
            'report': build_executive_report(result),
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))
