from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time


class SessionState:
    def __init__(self):
        self.lock = Lock()
        self.pending_messages = []
        self.running = False
        self.revision = 0
        self.generation = 0
        self.reply_callback = None
        self.error_callback = None


class SessionCoordinator:
    def __init__(
        self,
        generate_reply,
        save_exchange,
        max_workers=4,
        debounce_seconds=1.0,
        sleep_fn=time.sleep,
    ):
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise ValueError("max_workers must be a positive number.")
        if max_workers < 1:
            raise ValueError("max_workers must be a positive number.")
        if not isinstance(debounce_seconds, (int, float)) or debounce_seconds < 0:
            raise ValueError("debounce_seconds must not be negative.")

        self.generate_reply = generate_reply
        self.save_exchange = save_exchange
        self.debounce_seconds = debounce_seconds
        self.sleep_fn = sleep_fn
        self.states = {}
        self.states_lock = Lock()
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="sales-agent",
        )
        self.closed = False

    def submit(self, session_id, text, reply_callback, error_callback):
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must not be empty.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("message text must not be empty.")
        if not callable(reply_callback) or not callable(error_callback):
            raise ValueError("reply and error callbacks must be callable.")

        state = self._get_state(session_id)
        should_start = False

        with state.lock:
            state.pending_messages.append(text.strip())
            state.revision += 1
            state.reply_callback = reply_callback
            state.error_callback = error_callback

            if not state.running:
                state.running = True
                should_start = True

        if should_start:
            self.executor.submit(self._run_session, session_id, state)

    def reset_session(self, session_id, reset_history):
        if not callable(reset_history):
            raise ValueError("reset_history must be callable.")

        state = self._get_state(session_id)
        with state.lock:
            state.generation += 1
            state.revision += 1
            state.pending_messages.clear()
            state.reply_callback = None
            state.error_callback = None
            reset_history()

    def shutdown(self, wait=True):
        with self.states_lock:
            self.closed = True
        self.executor.shutdown(wait=wait, cancel_futures=True)

    def _get_state(self, session_id):
        with self.states_lock:
            if self.closed:
                raise RuntimeError("Session coordinator is closed.")
            if session_id not in self.states:
                self.states[session_id] = SessionState()
            return self.states[session_id]

    def _run_session(self, session_id, state):
        try:
            while True:
                self.sleep_fn(self.debounce_seconds)

                with state.lock:
                    if not state.pending_messages:
                        state.running = False
                        return

                    messages = list(state.pending_messages)
                    state.pending_messages.clear()
                    revision = state.revision
                    generation = state.generation
                    reply_callback = state.reply_callback

                restarted = False

                while True:
                    combined_text = "\n".join(messages)
                    reply = self.generate_reply(session_id, combined_text)

                    with state.lock:
                        if state.generation != generation:
                            break

                        has_new_messages = (
                            state.revision != revision and state.pending_messages
                        )
                        if has_new_messages and not restarted:
                            messages.extend(state.pending_messages)
                            state.pending_messages.clear()
                            revision = state.revision
                            reply_callback = state.reply_callback
                            restarted = True
                            continue

                        self.save_exchange(session_id, combined_text, reply)

                    reply_callback(reply)
                    break

                with state.lock:
                    if not state.pending_messages:
                        state.running = False
                        return
        except Exception as error:
            with state.lock:
                error_callback = state.error_callback
                state.pending_messages.clear()
                state.running = False

            if error_callback is not None:
                error_callback(error)
