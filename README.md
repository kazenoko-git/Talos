# Talos 2

A programmable embedded NPU project targeting a 2×2 GF180 tile budget: ternary weights, signed INT8 activations, and INT32 accumulation.

**Status: planning and development scaffold. No Talos 2 RTL or inference implementation exists yet.** Buffer size, accumulator count, output scaling, operating frequency, and memory parts still require validation.

## Start here

Read the [implementation plan](docs/talos2-implementation-plan.md). The first implementation task is the independent integer reference and weight packing; RTL follows a defined numerical contract.

## Repository layout

- `docs/`: implementation plan, architecture discussions, area estimates, and decisions.
- `src/`: future Talos 2 RTL and shuttle configuration.
- `test/`: simulation dependencies and future cocotb tests.
- `software/reference/`: future integer oracle and model exporter.
- `software/host/`: future host driver and examples.
- `hardware/`: carrier-board requirements and later design files.
- `scripts/`: development environment checks.
- `.devcontainer/`, `.vscode/`: development configuration inherited from the existing template.

## Local development

Install Python 3.11 or newer and Icarus Verilog, then run:

```sh
make setup
make check-env
```

`make setup` creates a local `.venv` and installs the pinned simulation dependencies. `make check-env` checks Python dependencies and Icarus availability; it is not an RTL test or an area/timing check. The inherited devcontainer is an alternative setup and has not been rebuilt for this scaffold.

No simulation, GDS, FPGA, or submission workflow is enabled yet. Add the Talos 2 top module, testbench, source lists, and reviewed shuttle configuration before enabling them. Do not carry over Talos 1's density/timing overrides by accident.

## Branches and local folders

All branches belong to [kazenoko-git/Talos](https://github.com/kazenoko-git/Talos):

- `talos_1`: the preserved implementation and planning snapshot; checked out in `../ttgf-verilog-template`.
- `main`: intentionally has no tracked files; prior history remains available.
- `talos_2`: this new project; checked out in `../talos`.

The folders are linked Git worktrees: they share history/remotes, while checked-out files and branches are separate. Use `git -C ../ttgf-verilog-template status` or `git -C ../talos status` to inspect each. Do not delete the original checkout's `.git` directory; this checkout depends on it. Use Git worktree commands when moving/removing either checkout.

The inherited Apache-2.0 license is retained. Follow the organizer's authorship and physical FPGA testing requirements recorded in the implementation plan.
