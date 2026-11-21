from prometheus_client import REGISTRY, Counter, Gauge, Histogram, Summary, Info, Enum
from prometheus_client import disable_created_metrics

# disable **_created metric.
disable_created_metrics()


def _m(cls, name, doc, labels=(), **kw):
    # Streamlit can re-import this module on reruns; reuse already-registered metrics.
    return REGISTRY._names_to_collectors.get(name) or cls(name, doc, labels, **kw)


# Counters
REQUESTS = _m(Counter, 'caption_requests', 'Caption requests per client', ['mode', 'client_ip', 'session_id'])
IMAGES = _m(Counter, 'caption_images_processed', 'Images processed', ['mode', 'status'])
ERRORS = _m(Counter, 'caption_errors', 'Errors by type', ['mode', 'error_type'])
SKIPPED = _m(Counter, 'caption_zip_entries_skipped', 'ZIP entries skipped', ['reason'])
UPLOAD_BYTES = _m(Counter, 'caption_uploaded_bytes', 'Bytes uploaded', ['mode'])
SESSIONS = _m(Counter, 'caption_sessions_started', 'New browser sessions', ['client_ip'])

# Gauges
ACTIVE = _m(Gauge, 'caption_active_requests', 'Requests in progress', ['mode'])
QUEUE = _m(Gauge, 'caption_bulk_queue_remaining', 'Images left in running bulk jobs')
MODEL_LOADED = _m(Gauge, 'caption_model_loaded', '1 when the model is loaded')
MODEL_LOAD_SECONDS = _m(Gauge, 'caption_model_load_seconds', 'Time taken to load the model')
MODEL_PARAMS = _m(Gauge, 'caption_model_parameters', 'Number of model parameters')
LAST_SUCCESS = _m(Gauge, 'caption_last_success_timestamp_seconds', 'Unix time of last successful caption')

# Histograms
INFERENCE = _m(Histogram, 'caption_inference_seconds', 'Model inference time per image', ['mode'],
               buckets=(0.1, 0.25, 0.5, 1, 1.5, 2, 3, 5, 8, 13, 20, 30))
IMAGE_BYTES = _m(Histogram, 'caption_image_bytes', 'Image file size', ['mode'],
                 buckets=(1e4, 5e4, 1e5, 2.5e5, 5e5, 1e6, 2.5e6, 5e6, 1e7))
CAPTION_WORDS = _m(Histogram, 'caption_length_words', 'Words per generated caption', ['mode'],
                   buckets=(2, 4, 6, 8, 10, 12, 15, 20, 30))
ZIP_IMAGES = _m(Histogram, 'caption_zip_images', 'Images per uploaded ZIP',
                buckets=(1, 5, 10, 25, 50, 100, 200))

# Summaries (_sum and _count)
REQUEST_SECONDS = _m(Summary, 'caption_request_seconds', 'End-to-end request time', ['mode'])
INPUT_BYTES = _m(Summary, 'caption_input_bytes', 'Request payload size (bytes)', ['mode'])
BULK_JOB_SECONDS = _m(Summary, 'caption_bulk_job_seconds', 'Time to process one whole ZIP')

# Info / Enum
BUILD = _m(Info, 'caption_app_build', 'Prometheus Instrumented Captioning App')
STATE = _m(Enum, 'caption_app_state', 'Current app state', states=['idle', 'loading_model', 'single', 'bulk'])
