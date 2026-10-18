#!/usr/bin/env python3
"""plannerd exec wrapper for the c3 shadow-test stack.

Forked plannerd (manager preimports all modules, then forks) segfaults inside
acados (LongMPC ctor -> AcadosOcpSolverCython -> long_acados_reset): the
capsule from malloc is uninitialized, and under the launch_env.sh Jetson
runtime tuning (PYTHONMALLOC=malloc PYTHONOPTIMIZE=1 MALLOC_ARENA_MAX=2 ...)
the long-lived manager heap hands acados a poisoned block; PYTHONOPTIMIZE=1
also strips the `assert acados_create(...) == 0` guard so a half-initialized
capsule segfaults instead of raising. Same code is stable in a fresh process.

Fix: re-exec a clean interpreter WITHOUT the allocator-affecting env vars.
exec resets the heap, and unsetting PYTHONOPTIMIZE restores asserts so any
future acados failure raises a diagnosable AssertionError instead of SIGSEGV.
exec keeps the same pid, so manager supervision is unaffected.
Created 2026-10-17.
"""
import os
import sys


def main():
  for k in ('PYTHONMALLOC', 'PYTHONOPTIMIZE', 'PYTHONHASHSEED',
            'MALLOC_ARENA_MAX', 'PYTHONNOUSERSITE'):
    os.unsetenv(k)
  os.execvp(sys.executable, [sys.executable, "-m", "openpilot.selfdrive.controls.plannerd"])


if __name__ == "__main__":
  main()
