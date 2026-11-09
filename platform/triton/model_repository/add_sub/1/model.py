"""Minimal Triton Python-backend model: OUTPUT0 = INPUT0 + INPUT1, OUTPUT1 = INPUT0 - INPUT1."""
import triton_python_backend_utils as pb_utils


class TritonPythonModel:
    def execute(self, requests):
        responses = []
        for request in requests:
            in0 = pb_utils.get_input_tensor_by_name(request, "INPUT0").as_numpy()
            in1 = pb_utils.get_input_tensor_by_name(request, "INPUT1").as_numpy()
            out0 = pb_utils.Tensor("OUTPUT0", (in0 + in1).astype(in0.dtype))
            out1 = pb_utils.Tensor("OUTPUT1", (in0 - in1).astype(in0.dtype))
            responses.append(pb_utils.InferenceResponse(output_tensors=[out0, out1]))
        return responses
