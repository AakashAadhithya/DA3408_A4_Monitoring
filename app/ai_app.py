#!/usr/bin/env python3
# streamlit run app/ai_app.py   -> app on :8501, metrics on :18000/metrics

import io
import os
import time
import logging
import zipfile

import pandas as pd
import streamlit as st
from PIL import Image
from prometheus_client import start_http_server
from streamlit.runtime.scriptrunner import get_script_run_ctx

import metrics as M

MODEL_NAME = os.getenv("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
METRICS_PORT = int(os.getenv("METRICS_PORT", "18000"))
MAX_ZIP_IMAGES = 200
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif")

log = logging.getLogger("AI_app")
log.setLevel(logging.INFO)
if not log.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    log.addHandler(ch)


@st.cache_resource
def start_metrics_server():
    log.info(f"starting the prometheus monitor at port {METRICS_PORT}")
    try:
        start_http_server(METRICS_PORT)
    except OSError:
        log.warning("metrics port already in use, assuming server is running")


@st.cache_resource(show_spinner="Loading captioning model...")
def load_model():
    import torch
    from transformers import BlipProcessor, BlipForConditionalGeneration

    M.STATE.state('loading_model')
    start = time.time()
    processor = BlipProcessor.from_pretrained(MODEL_NAME)
    model = BlipForConditionalGeneration.from_pretrained(MODEL_NAME).eval()
    M.MODEL_LOAD_SECONDS.set(time.time() - start)
    M.MODEL_PARAMS.set(sum(p.numel() for p in model.parameters()))
    M.MODEL_LOADED.set(1)
    M.BUILD.info({'version': '1.0.0', 'model': MODEL_NAME, 'device': 'cpu',
                  'torch': torch.__version__, 'author': 'Aakash Aadhithya (DA24B028)'})
    M.STATE.state('idle')
    return processor, model


def caption(raw: bytes, mode: str) -> str:
    import torch
    processor, model = load_model()
    M.IMAGE_BYTES.labels(mode).observe(len(raw))
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((512, 512))  # bound CPU/RAM cost per image
    with M.INFERENCE.labels(mode).time():
        inputs = processor(images=img, return_tensors="pt")
        with torch.inference_mode():
            out = model.generate(**inputs, max_new_tokens=30)
        text = processor.decode(out[0], skip_special_tokens=True)
    M.CAPTION_WORDS.labels(mode).observe(len(text.split()))
    M.IMAGES.labels(mode, 'success').inc()
    M.LAST_SUCCESS.set_to_current_time()
    return text


def track_request(mode: str, nbytes: int):
    M.REQUESTS.labels(mode, client_ip(), session_id()).inc()
    M.UPLOAD_BYTES.labels(mode).inc(nbytes)
    M.INPUT_BYTES.labels(mode).observe(nbytes)


def fail(mode: str, err: Exception):
    M.IMAGES.labels(mode, 'failed').inc()
    M.ERRORS.labels(mode, type(err).__name__).inc()
    log.warning(f"{mode}: {type(err).__name__}: {err}")


def client_ip() -> str:
    return st.context.ip_address or "localhost"


def session_id() -> str:
    ctx = get_script_run_ctx()
    return ctx.session_id[:8] if ctx else "unknown"


def single_mode():
    f = st.file_uploader("Upload an image", type=[e[1:] for e in IMAGE_EXT])
    if f and st.button("Generate caption", type="primary"):
        raw = f.getvalue()
        track_request('single', len(raw))
        M.STATE.state('single')
        with M.ACTIVE.labels('single').track_inprogress(), M.REQUEST_SECONDS.labels('single').time():
            try:
                text = caption(raw, 'single')
                st.image(raw, width=400)
                st.success(text)
            except Exception as e:
                fail('single', e)
                st.error(f"Could not caption this image: {e}")
        M.STATE.state('idle')


def zip_entries(z: zipfile.ZipFile):
    keep = []
    for i in z.infolist():
        name = os.path.basename(i.filename)
        if i.is_dir() or i.filename.startswith("__MACOSX") or name.startswith("."):
            continue
        if not name.lower().endswith(IMAGE_EXT):
            M.SKIPPED.labels('not_image').inc()
        elif i.file_size > MAX_IMAGE_BYTES:
            M.SKIPPED.labels('too_large').inc()
        else:
            keep.append(i)
    if len(keep) > MAX_ZIP_IMAGES:
        M.SKIPPED.labels('over_limit').inc(len(keep) - MAX_ZIP_IMAGES)
        st.warning(f"Only the first {MAX_ZIP_IMAGES} images will be processed.")
        keep = keep[:MAX_ZIP_IMAGES]
    return keep


def bulk_mode():
    f = st.file_uploader("Upload a ZIP of images", type=["zip"])
    if not (f and st.button("Caption all images", type="primary")):
        return
    track_request('bulk', f.size)
    try:
        z = zipfile.ZipFile(f)
    except zipfile.BadZipFile as e:
        M.ERRORS.labels('bulk', 'BadZipFile').inc()
        st.error(f"Invalid ZIP file: {e}")
        return

    entries = zip_entries(z)
    M.ZIP_IMAGES.observe(len(entries))
    if not entries:
        st.warning("No images found in the ZIP.")
        return

    M.STATE.state('bulk')
    M.QUEUE.inc(len(entries))
    rows, bar = [], st.progress(0.0)
    with M.ACTIVE.labels('bulk').track_inprogress(), M.REQUEST_SECONDS.labels('bulk').time(), \
            M.BULK_JOB_SECONDS.time():
        for k, info in enumerate(entries, 1):
            try:
                text, status = caption(z.read(info), 'bulk'), 'ok'
            except Exception as e:
                fail('bulk', e)
                text, status = "", f"failed: {type(e).__name__}"
            rows.append({"file": info.filename, "caption": text, "status": status})
            M.QUEUE.dec()
            bar.progress(k / len(entries), text=f"{k}/{len(entries)}  {info.filename}")
    M.STATE.state('idle')

    df = pd.DataFrame(rows)
    st.dataframe(df)
    st.download_button("Download CSV", df.to_csv(index=False), "captions.csv", "text/csv", on_click="ignore")


def main():
    st.set_page_config(page_title="CPU Image Captioning", page_icon="🖼️")
    start_metrics_server()
    if "seen" not in st.session_state:
        st.session_state.seen = True
        M.SESSIONS.labels(client_ip()).inc()

    st.title("CPU Image Captioning")
    st.caption(f"Model: `{MODEL_NAME}` · Metrics: `:{METRICS_PORT}/metrics` · Session: `{session_id()}`")
    load_model()

    single, bulk = st.tabs(["Single image", "Bulk (ZIP)"])
    with single:
        single_mode()
    with bulk:
        bulk_mode()


main()
