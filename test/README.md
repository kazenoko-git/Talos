# Verification workspace

`requirements.txt` pins the inherited cocotb/pytest dependencies. Use `make setup` and `make check-env` from the repository root.

There are no Talos 2 RTL tests yet. First build the independent software oracle, then test arithmetic boundaries, packing, tails, host serial edges, memory transactions, and layer sequencing as described in the implementation plan. Add a local simulation Makefile and testbench when the first RTL module is ready; explicitly list every test module in CI.

Talos 1 tests remain on `talos_1`. They validate that design, not the new NPU.
