"""Real isolated subprocess identity, without opening the game or network."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from host_runtime.contracts import ContractError
from host_runtime.python_runtime import ROOT, interpreter, script_command


@contextmanager
def trusted_probe(source):
    # This exact temporary script is the sole file removed by this helper.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".py", prefix="identity_probe_", dir=ROOT / "integration", delete=False) as stream:
        stream.write(source)
        path = Path(stream.name)
    try:
        yield path
    finally:
        assert path.parent.resolve() == (ROOT / "integration").resolve()
        path.unlink(missing_ok=True)


class PythonRuntimeTests(unittest.TestCase):
    def test_actual_child_pid_is_the_interpreter_owner(self):
        source = """import json,os,sys
from host_runtime.desktop_backend import NativeHostSpawner
print(json.dumps(dict(pid=os.getpid(),executable=sys.executable,prefix=sys.prefix,argv=sys.argv,identity=NativeHostSpawner.identity(os.getpid()) if os.name=='nt' else None)),flush=True)
sys.stdin.readline()
"""
        with trusted_probe(source) as script:
            environment = dict(os.environ, PYTHONHOME="Z:/not-a-runtime", PYTHONPATH="Z:/not-a-runtime")
            child = subprocess.Popen(script_command(script, ["literal argument"]), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                line = child.stdout.readline()
                self.assertTrue(line, child.stderr.read() if child.poll() is not None else "probe did not respond")
                result = json.loads(line)
                self.assertEqual(child.pid, result["pid"])
                self.assertEqual(interpreter(), Path(result["executable"]).resolve())
                self.assertEqual(Path(sys.prefix).resolve(), Path(result["prefix"]).resolve())
                self.assertEqual(result["argv"], [str(script), "literal argument"])
                if os.name == "nt":
                    from host_runtime.desktop_backend import NativeHostSpawner
                    self.assertEqual(result["identity"], NativeHostSpawner.identity(child.pid))
                child.communicate("done\n", timeout=10)
                self.assertEqual(child.returncode, 0)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=10)

    def test_explicit_trusted_interpreter_preserves_isolation_and_venv_packages(self):
        source = """import json,sys,pydantic_ai
print(json.dumps(dict(executable=sys.executable,isolated=sys.flags.isolated,no_site=sys.flags.no_site,no_bytecode=sys.dont_write_bytecode,package=pydantic_ai.__file__)))
"""
        with trusted_probe(source) as script:
            result = subprocess.run(script_command(script, python=interpreter()), capture_output=True, text=True, encoding="utf-8", timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 0, result.stderr)
            observed = json.loads(result.stdout)
            self.assertTrue(observed["isolated"])
            self.assertTrue(observed["no_site"])
            self.assertTrue(observed["no_bytecode"])
            self.assertTrue(Path(observed["package"]).resolve().is_relative_to(Path(sys.prefix).resolve() / "Lib/site-packages"))

    def test_outside_script_is_rejected_before_execution(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as stream:
            outside = Path(stream.name)
        try:
            with self.assertRaises(ContractError):
                script_command(outside)
        finally:
            outside.unlink()


if __name__ == "__main__":
    unittest.main()
