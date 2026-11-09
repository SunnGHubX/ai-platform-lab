package main

# ---- fixtures ----
good_deploy := {
	"kind": "Deployment",
	"metadata": {"name": "api"},
	"spec": {"template": {"spec": {
		"securityContext": {"runAsNonRoot": true},
		"containers": [{
			"name": "api",
			"image": "ghcr.io/acme/api:1.2.3",
			"readinessProbe": {"httpGet": {"path": "/readyz", "port": 8080}},
			"resources": {"limits": {"memory": "256Mi"}},
		}],
	}}},
}

with_container(patch) := object.union(good_deploy, {"spec": {"template": {"spec": {"containers": [object.union(good_deploy.spec.template.spec.containers[0], patch)]}}}})

# ---- tests ----
test_good_deployment_passes if {
	count(deny) == 0 with input as good_deploy
	count(warn) == 0 with input as good_deploy
}

test_latest_tag_denied if {
	msgs := deny with input as with_container({"image": "nginx:latest"})
	some msg in msgs
	contains(msg, ":latest")
}

test_untagged_image_denied if {
	msgs := deny with input as with_container({"image": "nginx"})
	some msg in msgs
	contains(msg, "no image tag")
}

test_digest_pinned_image_allowed if {
	count(deny) == 0 with input as with_container({"image": "nginx@sha256:abc123"})
}

test_missing_memory_limit_denied if {
	# object.union merges nested objects, so remove resources first, then set CPU only
	c := object.union(object.remove(good_deploy.spec.template.spec.containers[0], ["resources"]), {"resources": {"limits": {"cpu": "1"}}})
	pod := object.union(good_deploy, {"spec": {"template": {"spec": {"containers": [c]}}}})
	msgs := deny with input as pod
	some msg in msgs
	contains(msg, "memory limit")
}

test_privileged_denied if {
	msgs := deny with input as with_container({"securityContext": {"privileged": true}})
	some msg in msgs
	contains(msg, "privileged")
}

test_host_network_denied if {
	pod := object.union(good_deploy, {"spec": {"template": {"spec": {"hostNetwork": true}}}})
	msgs := deny with input as pod
	some msg in msgs
	contains(msg, "hostNetwork")
}

test_gpu_without_toleration_denied if {
	msgs := deny with input as with_container({"resources": {"limits": {"memory": "1Gi", "nvidia.com/gpu": 1}}})
	some msg in msgs
	contains(msg, "does not tolerate")
}

test_gpu_with_toleration_allowed if {
	gpu := with_container({"resources": {"limits": {"memory": "1Gi", "nvidia.com/gpu": 1}, "requests": {"nvidia.com/gpu": 1}}})
	pod := object.union(gpu, {"spec": {"template": {"spec": {"tolerations": [{"key": "nvidia.com/gpu", "operator": "Exists"}]}}}})
	count(deny) == 0 with input as pod
}

test_gpu_request_limit_mismatch_denied if {
	gpu := with_container({"resources": {"limits": {"memory": "1Gi", "nvidia.com/gpu": 2}, "requests": {"nvidia.com/gpu": 1}}})
	pod := object.union(gpu, {"spec": {"template": {"spec": {"tolerations": [{"key": "nvidia.com/gpu"}]}}}})
	msgs := deny with input as pod
	some msg in msgs
	contains(msg, "request != limit")
}

test_missing_probe_warns if {
	c := object.remove(good_deploy.spec.template.spec.containers[0], ["readinessProbe"])
	pod := object.union(good_deploy, {"spec": {"template": {"spec": {"containers": [c]}}}})
	msgs := warn with input as pod
	some msg in msgs
	contains(msg, "readinessProbe")
}

test_root_warns_but_does_not_deny if {
	pod := json.remove(good_deploy, ["spec/template/spec/securityContext"])
	msgs := warn with input as pod
	some msg in msgs
	contains(msg, "runAsNonRoot")
	count(deny) == 0 with input as pod
}

test_public_lb_warns if {
	svc := {"kind": "Service", "metadata": {"name": "web"}, "spec": {"type": "LoadBalancer"}}
	msgs := warn with input as svc
	some msg in msgs
	contains(msg, "LoadBalancer")
}

test_non_workloads_ignored if {
	count(deny) == 0 with input as {"kind": "ConfigMap", "metadata": {"name": "x"}, "data": {}}
}
