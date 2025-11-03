# voice_alert.py
import threading, queue, time
import winsound, pyttsx3


class VoiceAlert:
    """
    Thread-safe, persistent voice alert queue.
    Plays a beep and speaks every message sequentially.
    """

    def __init__(self, rate: int = 185, beep_freq: int = 1200, beep_ms: int = 300):
        self.rate = rate
        self.beep_freq = beep_freq
        self.beep_ms = beep_ms
        self._queue = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def alert(self, message: str):
        """Add message to queue — non-blocking."""
        self._queue.put(message)

    def _speak(self, text: str):
        """Speak safely using a new engine each time."""
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print("TTS error:", e)

    def _beep(self):
        try:
            winsound.Beep(self.beep_freq, self.beep_ms)
        except Exception:
            pass

    def _worker_loop(self):
        """Process alerts sequentially forever."""
        while True:
            message = self._queue.get()
            try:
                self._beep()
                # Small delay so speech doesn’t cut the beep
                time.sleep(0.05)
                self._speak(message)
            except Exception as e:
                print("VoiceAlert worker error:", e)
            finally:
                self._queue.task_done()
                # small rest to avoid CPU hogging
                time.sleep(0.05)
