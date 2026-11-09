# Conftest policies for Kubernetes workloads (Rego v1 syntax, OPA >= 1.0).
# Run:  kubectl kustomize platform/vllm | conftest test --policy policy/kubernetes -
# Test: conftest verify --policy policy/kubernetes
package main

workload_kinds := {"Deployment", "StatefulSet", "DaemonSet", "Job"}

pod_spec := input.spec.template.spec if workload_kinds[input.kind]

pod_spec := input.spec.jobTemplate.spec.template.spec if input.kind == "CronJob"

containers contains c if {
	some c in pod_spec.containers
}

containers contains c if {
	some c in pod_spec.initContainers
}

name := sprintf("%s/%s", [input.kind, input.metadata.name])

# ---------------------------------------------------------------- deny (blocks the PR)

deny contains msg if {
	some c in containers
	endswith(c.image, ":latest")
	msg := sprintf("%s: container %q uses the mutable :latest tag", [name, c.name])
}

deny contains msg if {
	some c in containers
	not contains(c.image, ":")
	not contains(c.image, "@sha256")
	msg := sprintf("%s: container %q has no image tag or digest", [name, c.name])
}

deny contains msg if {
	some c in containers
	not c.resources.limits.memory
	msg := sprintf("%s: container %q has no memory limit (OOM blast radius is the whole node)", [name, c.name])
}

deny contains msg if {
	some c in containers
	c.securityContext.privileged == true
	msg := sprintf("%s: container %q is privileged", [name, c.name])
}

deny contains msg if {
	some c in containers
	c.securityContext.allowPrivilegeEscalation == true
	msg := sprintf("%s: container %q allows privilege escalation", [name, c.name])
}

deny contains msg if {
	some field in ["hostNetwork", "hostPID", "hostIPC"]
	pod_spec[field] == true
	msg := sprintf("%s: pod uses %s", [name, field])
}

# AI-specific: a GPU request without the GPU toleration never schedules on a tainted GPU pool,
# and burns a debugging hour every time.
deny contains msg if {
	some c in containers
	c.resources.limits["nvidia.com/gpu"]
	not tolerates_gpu_taint
	msg := sprintf("%s: requests nvidia.com/gpu but does not tolerate the nvidia.com/gpu taint", [name])
}

# AI-specific: GPU limit and request must match (extended resources can't be overcommitted).
deny contains msg if {
	some c in containers
	c.resources.requests["nvidia.com/gpu"]
	c.resources.requests["nvidia.com/gpu"] != c.resources.limits["nvidia.com/gpu"]
	msg := sprintf("%s: container %q nvidia.com/gpu request != limit", [name, c.name])
}

tolerates_gpu_taint if {
	some t in pod_spec.tolerations
	t.key == "nvidia.com/gpu"
}

# ---------------------------------------------------------------- warn (reported, not blocking)

warn contains msg if {
	some c in pod_spec.containers
	not c.readinessProbe
	msg := sprintf("%s: container %q has no readinessProbe", [name, c.name])
}

warn contains msg if {
	workload_kinds[input.kind]
	not runs_as_non_root
	msg := sprintf("%s: runAsNonRoot is not set (fine for vendor GPU images, not for our own services)", [name])
}

runs_as_non_root if pod_spec.securityContext.runAsNonRoot == true

runs_as_non_root if {
	every c in pod_spec.containers {
		c.securityContext.runAsNonRoot == true
	}
}

warn contains msg if {
	input.kind == "Service"
	input.spec.type == "LoadBalancer"
	not input.metadata.annotations["service.beta.kubernetes.io/aws-load-balancer-scheme"]
	msg := sprintf("Service/%s: LoadBalancer without an explicit scheme (internet-facing by default?)", [input.metadata.name])
}
