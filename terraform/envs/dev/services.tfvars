services = {
  # OpenAI-compatible gateway in front of vLLM / Triton
  inference-gateway = {
    namespace = "inference"
    secrets   = ["hf-token"]
  }

  # Queue-driven batch job: KEDA scales it on SQS depth, writes embeddings to S3
  batch-embedder = {
    namespace = "inference"
    queue     = { autoscale = true, visibility_timeout_seconds = 900 }
    bucket    = { versioning = false }
  }

  # MLflow: artifacts in S3, metadata in Postgres (replaces the lab's SQLite + PVC)
  mlflow = {
    namespace = "mlops"
    ecr       = false # uses the upstream image
    bucket    = {}
    postgres  = { instance_class = "db.t4g.micro" }
  }
}
