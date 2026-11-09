#!/usr/bin/env python3
"""Emit a fake 'inference' span + counter over OTLP/HTTP to the collector."""
import random
import time

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

ENDPOINT = "http://localhost:4318"
resource = Resource.create({"service.name": "demo-inference-client"})

tp = TracerProvider(resource=resource)
tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{ENDPOINT}/v1/traces")))
trace.set_tracer_provider(tp)

reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=f"{ENDPOINT}/v1/metrics"), export_interval_millis=5000)
metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

tracer = trace.get_tracer(__name__)
requests_counter = metrics.get_meter(__name__).create_counter("inference_requests", description="fake inference calls")

for i in range(20):
    with tracer.start_as_current_span("chat_completion") as span:
        model = random.choice(["qwen", "llama"])
        span.set_attribute("llm.model", model)
        time.sleep(random.uniform(0.05, 0.3))
        requests_counter.add(1, {"model": model})
    print(f"sent {i + 1}/20")

tp.shutdown()
metrics.get_meter_provider().shutdown()
