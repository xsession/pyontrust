GNU Radio Integration
=====================

This repo can optionally use `GNU Radio <https://www.gnuradio.org/>`_.

On Windows, GNU Radio is typically installed via Conda/Mamba (not pip).

Install (Windows, Conda)
------------------------

1) Install Miniforge/Mambaforge.

2) Create and activate an environment:

.. code-block:: powershell

   conda create -n gnuradio -c conda-forge python=3.11 gnuradio
   conda activate gnuradio

3) Verify GNU Radio imports:

.. code-block:: powershell

   python -c "from gnuradio import gr; print('GNU Radio OK')"

4) Run `pyontrust_gui` in that same environment (so it can import `gnuradio`):

.. code-block:: powershell

   Set-Location C:\GIT\pyontrust
   python -m pip install -U pip
   python -m pip install -r scripts\requirements.txt
   python -m pip install -e gui_app\nicegui_control
   python -m pyontrust_gui

Notes
-----

- The optional `gnuradio_module/` package provides a NiceGUI UI for running `.py` and `.grc` flowgraphs using:

   - the current Python interpreter,
   - another Python executable, or
   - a Conda env (`conda run -n ...`).

- For SDR interoperability, the SDR module can optionally bridge IQ over ZMQ (install `sdr_module[zmq]`) and GNU Radio can use its ZMQ blocks.
