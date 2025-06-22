from abc import abstractmethod
from queue import Queue


class CaptureBase:
    def __init__(self):
        self.cap = None

    @abstractmethod
    def __call__(self, frame_queue: Queue, ir_frame_queue: Queue) -> None:
        """
        Capture frames from a capture device and put them into a queue.
        This function is to be run in a Thread.
        :param frame_queue: A Queue[np.ndarray] to put the captured frames into
        :return: None, results are put into the frame_queue
        """
        pass
