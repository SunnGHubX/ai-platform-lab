services = {
  inference-gateway = {
    namespace = "inference"
    secrets   = ["hf-token", "api-keys"]
  }

  batch-embedder = {
    namespace = "inference"
    queue     = { autoscale = true, visibility_timeout_seconds = 900, max_receive_count = 3 }
    bucket    = { noncurrent_expiration_days = 90 }
  }

  mlflow = {
    namespace = "mlops"
    ecr       = false
    bucket    = { noncurrent_expiration_days = 180 }
    postgres  = { instance_class = "db.r7g.large", allocated_storage = 100, multi_az = true } # validation enforces multi_az in prod
  }
}
