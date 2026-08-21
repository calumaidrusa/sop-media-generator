from pathlib import Path
import shutil
import tempfile
import base64
import io
import json
import zipfile

from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import JSONResponse, StreamingResponse
from faster_whisper import WhisperModel
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).parent
app = FastAPI(title="SOP Studio Local")
model = None


def get_model():
    global model
    if model is None:
        model = WhisperModel("base", device="cpu", compute_type="int8")
    return model


@app.post("/api/transcribe")
async def transcribe_video(video: UploadFile = File(...)):
    suffix = Path(video.filename or "video.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        shutil.copyfileobj(video.file, temp)
        temp_path = Path(temp.name)
    try:
        segments, info = get_model().transcribe(str(temp_path), language="zh", vad_filter=True, beam_size=3)
        result = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments if s.text.strip()]
        return JSONResponse({"language": info.language, "duration": info.duration, "segments": result})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/api/export-zip")
async def export_zip(request: Request):
    project = await request.json()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        frames = project.pop("frames", [])
        archive.writestr("sop-studio-project.json", json.dumps(project | {"frameCount": len(frames)}, ensure_ascii=False, indent=2))
        markdown = [f"# {project.get('topic') or '未命名 SOP'}", "", f"共 {len(project.get('steps', []))} 個步驟", ""]
        for index, step in enumerate(project.get("steps", []), 1):
            markdown += [f"## {index:02d}. {step.get('title', '')}", "", step.get("copy", ""), "", f"- 類型：{step.get('tag', '')}", f"- 提醒：{step.get('note', '')}", f"- 操作畫面：{'已配畫面' if step.get('frameId') else '尚未指定'}", ""]
        archive.writestr("sop-studio-project.md", "\n".join(markdown))
        for index, frame in enumerate(frames, 1):
            data_url = frame.get("dataUrl", "")
            if "," in data_url:
                archive.writestr(f"frames/frame-{index:02d}.jpg", base64.b64decode(data_url.split(",", 1)[1]))
    output.seek(0)
    return StreamingResponse(output, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=sop-studio-project.zip"})


app.mount("/", StaticFiles(directory=ROOT, html=True), name="static")
