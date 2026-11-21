# DA3408 A4 — Application Monitoring with Prometheus & Grafana

A Streamlit app that captions images on the CPU (`Salesforce/blip-image-captioning-base`) and is instrumented with `prometheus_client`. Prometheus scrapes it together with `node_exporter`, sends alerts to Alertmanager, and a provisioned Grafana dashboard shows everything.

**Aakash Aadhithya — DA24B028**

```
.
├── app/
│   ├── ai_app.py            # Streamlit app: Single + Bulk (ZIP) modes
│   └── metrics.py           # all Prometheus metrics
├── prometheus/
│   ├── prometheus.yml       # scrape config: node, python_app, prometheus
│   ├── rules.yml            # recording + alerting rules
│   └── alertmanager.yml
├── grafana/
│   ├── dashboards/caption_app_dashboard.json   # dashboard JSON export
│   └── provisioning/        # datasource + dashboard auto-provisioning
├── scripts/
│   ├── setup.sh             # downloads binaries, installs Grafana + Python deps
│   ├── start.sh             # starts the whole stack
│   └── make_sample_zip.py   # builds a test ZIP
└── requirements.txt
```

## Ports

| Service | Port |
|---|---|
| Streamlit app | 8501 |
| App `/metrics` | 18000 |
| node_exporter | 9100 |
| Prometheus | 9090 |
| Alertmanager | 9093 |
| Grafana (admin/admin) | 3000 |

## Run (Ubuntu, amd64 or arm64)

```bash
scripts/setup.sh                       # one time
scripts/start.sh                       # starts the stack; Ctrl+C stops it
python scripts/make_sample_zip.py -n 40   # test ZIP (includes 1 corrupt + 1 non-image file)
```

You need internet the first time the app runs, to download the model (~1 GB).
Open Grafana → **DA3408 → DA3408 A4 · CPU Image Captioning — Observability** (refreshes every 5 s).
To receive alerts, set your own webhook.site URL in `prometheus/alertmanager.yml`.

To run the pieces by hand:
```bash
bin/node_exporter/node_exporter
bin/prometheus/prometheus --config.file=prometheus/prometheus.yml
bin/alertmanager/alertmanager --config.file=prometheus/alertmanager.yml
cd app && streamlit run ai_app.py
```

## Metrics

| Type | Metric | Labels |
|---|---|---|
| Counter | `caption_requests_total` | `mode`, `client_ip`, `session_id` |
| Counter | `caption_images_processed_total` | `mode`, `status` |
| Counter | `caption_errors_total` | `mode`, `error_type` |
| Counter | `caption_zip_entries_skipped_total` | `reason` |
| Counter | `caption_uploaded_bytes_total` | `mode` |
| Counter | `caption_sessions_started_total` | `client_ip` |
| Gauge | `caption_active_requests` | `mode` |
| Gauge | `caption_bulk_queue_remaining`, `caption_model_loaded`, `caption_model_load_seconds`, `caption_model_parameters`, `caption_last_success_timestamp_seconds` | – |
| Histogram | `caption_inference_seconds`, `caption_image_bytes`, `caption_length_words` | `mode` |
| Histogram | `caption_zip_images` | – |
| Summary (`_sum`, `_count`) | `caption_request_seconds`, `caption_input_bytes` | `mode` |
| Summary | `caption_bulk_job_seconds` | – |
| Info / Enum | `caption_app_build`, `caption_app_state` | – |

On Linux, `prometheus_client` also exports `process_*` metrics (RSS, CPU seconds, open files) and `python_gc_*` metrics.

**Client tracking:** `client_ip` comes from `st.context.ip_address` and is `localhost` for local access. `session_id` is the first 8 characters of the Streamlit session ID, so every browser tab counts as a separate client. Open the app from your Mac's browser at the VM's IP to see a real client IP.

## Alerts (`prometheus/rules.yml`)

- **critical:** `CaptionAppDown`, `NodeExporterDown`, `HighMemoryUsage`
- **warning:** `HighInferenceLatency` (p95 > 5 s), `HighCaptionErrorRate` (> 10 %), `BulkBacklog`, `AppMemoryHigh`, `HighCPUUsage` (> 85 % for 30 s, which a bulk ZIP usually triggers), `DiskAlmostFull`

## Dashboard

The dashboard is laid out top to bottom, from high-level health down to low-level resources:

1. **Service health:** up/down status, model status, totals, failure rate, a table of firing alerts
2. **Traffic:** throughput and requests per mode, requests per client/session, upload volume
3. **Latency:** p50/p90/p99 from the histogram, Summary vs Histogram means, a latency heatmap, bulk job duration
4. **Inputs & outputs:** distributions of image size and caption length, skipped ZIP entries, errors by type
5. **App ↔ system correlation:** images/s vs CPU %, app RSS vs node memory, queue vs load average (dual axes)
6. **System:** CPU by mode, memory, disk usage, disk I/O, network

How the dashboard follows the Seven Commandments:
- **Colour-blind-safe colours:** Okabe–Ito palette; the heatmap uses Cividis.
- **Works in print and PDF too:** point markers are always on, bulk is dashed and single is solid, and status panels show text (UP/DOWN) as well as colour.
- **Named axes, with scale and units:** every axis label gives the quantity, the unit and the scale, e.g. `Inference latency (seconds) · log₂ scale`.
- **Legends:** shown as tables (last, mean, max) wherever a panel has more than one series.
- **Titles and subtitles:** every title is written as `Title · subtitle`.
- **A story for each panel:** each panel has a description (ⓘ), and a "How to read" note sits at the top of the dashboard.

**For the video:** set the time range to *Last 5 minutes* with a 5 s refresh. Caption a few single images, then upload the sample ZIP. The bulk plateau in ② should line up with the CPU rise in ⑤ and ⑥.

## Evidence

Screenshots of the running stack are in [`evidence/`](evidence/) (app, `/metrics`, node_exporter, Prometheus targets and alerts, Alertmanager/webhook, Grafana rows).
