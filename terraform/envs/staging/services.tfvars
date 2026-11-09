services = {
  inference-gateway = {
    namespace = "inference"
    secrets   = ["hf-token"]
  }

  batch-embedder = {
    namespace = "inference"
    queue     = { autoscale = true, visibility_timeout_seconds = 900 }
    bucket    = {}
  }

  mlflow = {
    namespace = "mlops"
    ecr       = false
    bucket    = {}
    postgres  = { instance_class = "db.t4g.medium", allocated_storage = 50 }
  }
}
