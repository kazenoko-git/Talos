# Integer reference and exporter

First deliverable: an independent unpacked ternary matrix-vector oracle with signed INT8 inputs, INT32 accumulation/bias, and explicitly defined output rounding/saturation.

Then add the tiled packed representation and verify exact agreement with the oracle. Include a 5-output × 65-input case, −128 negation, bias applied once across chunks, invalid weight codes, output tails, and saturation boundaries. Keep direct mathematical evaluation independent of the RTL traversal.
