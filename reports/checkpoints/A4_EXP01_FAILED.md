# PRAHARI-AI — Checkpoint: A4_EXP01_FAILED

Error: CUDA error: out of memory
CUDA kernel errors might be asynchronously reported at some other API call, so the stacktrace below might be incorrect.
For debugging consider passing CUDA_LAUNCH_BLOCKING=1
Compile with `TORCH_USE_CUDA_DSA` to enable device-side assertions.

Traceback:
Traceback (most recent call last):
  File "D:\PRAHARI-AI\training\run_exp01_conservative.py", line 237, in main
    results = model.train(
              ^^^^^^^^^^^^
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\ultralytics\engine\model.py", line 852, in train
    self.trainer.train()
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\ultralytics\engine\trainer.py", line 244, in train
    self._do_train()
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\ultralytics\engine\trainer.py", line 426, in _do_train
    self._setup_train()
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\ultralytics\engine\trainer.py", line 318, in _setup_train
    self.model = self.model.to(self.device)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\torch\nn\modules\module.py", line 1340, in to
    return self._apply(convert)
           ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\ultralytics\nn\tasks.py", line 301, in _apply
    super()._apply(fn)
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\torch\nn\modules\module.py", line 900, in _apply
    module._apply(fn)
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\torch\nn\modules\module.py", line 900, in _apply
    module._apply(fn)
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\torch\nn\modules\module.py", line 900, in _apply
    module._apply(fn)
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\torch\nn\modules\module.py", line 927, in _apply
    param_applied = fn(param)
                    ^^^^^^^^^
  File "C:\Users\acer\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\torch\nn\modules\module.py", line 1326, in convert
    return t.to(
           ^^^^^
RuntimeError: CUDA error: out of memory
CUDA kernel errors might be asynchronously reported at some other API call, so the stacktrace below might be incorrect.
For debugging consider passing CUDA_LAUNCH_BLOCKING=1
Compile with `TORCH_USE_CUDA_DSA` to enable device-side assertions.


