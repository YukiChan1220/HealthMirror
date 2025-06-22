# Local rPPG Inference with ONNX Models

***Note: This repository has only been tested with python 3.12.***

## Usage
- `pip install -r requirements.txt`
- `python main.py`

## Structure
- `main.py`: The main script to run the pipeline with both the SHELL and GUI.
- `global_vars.py`: A global interrupt flag to stop the pipeline is defined here.
- `capture/`
- - `base.py`: The base class for collecting raw frames.
- - `camera.py`: The class for collecting frames from a camera.
- `preprocess/`
- - `base.py`: The base class for preprocessing raw frames.
- - `mp.py`: The class for preprocessing frames with *MediaPipe Face Mesh*.
- `model/`
- - `base.py`: The base class for loading and using models.
- - `step.py`: The class for using the `Step` model.
- - `physnet.py`: The class for using the `PhysNet` model.
- - `models/onnx/`
- - - `step.onnx`: The ONNX model for the `Step` model.
- - - `state.pkl`: Pickled initial state parameters for the `Step` model.
- - - `physnet.onnx`: The ONNX model for the `PhysNet` model.
- `display/`
- - `base.py`: The base class for saving the results.
- - `log_only.py`: The class for saving the results in a log file.
- - `log_and_print.py`: The class for saving the results in a log file and printing the results to the console.

## Explanation
- *capture device index*: An integer to specify the camera device to use. For example, `0` for the first camera, `1` for the second camera, and so on. A path to a video file can also be specified, but reading from a video file is not yet implemented with frame rate control. ***Note: Only 30fps cameras are supported at present.***
- *models*: `Step` and `PhysNet` are supported at present.
- - `Step`: A model that takes one frame at a time as input. Frame size should be 36x36.
- - `PhysNet`: A model that takes 128 frames at a time as input. Frame size should be 32x32.

## About models
Models have been trained and packed to ONNX format. Find them at `model/models`.
