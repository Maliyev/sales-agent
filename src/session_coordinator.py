from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time

from app_logging import get_logger


logger = get_logger("sessions")

FAILURE_STATUS_BY_STAGE = {
    "generate": "FAILED_LLM_API",
    "save": "FAILED_OTHER",
    "deliver": "FAILED_DELIVERY",
}


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
        save_reply,
        mark_messages_status=None,
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
        if mark_messages_status is not None and not callable(mark_messages_status):
            raise ValueError("mark_messages_status must be callable.")

        self.generate_reply = generate_reply
        self.save_reply = save_reply
        self.mark_messages_status = mark_messages_status
        self.debounce_seconds = debounce_seconds
        self.sleep_fn = sleep_fn
        self.states = {}
        self.states_lock = Lock()
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="sales-agent",
        )
        self.closed = False

    def submit(self, session_id, message_id, text, reply_callback, error_callback):
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must not be empty.")
        if isinstance(message_id, bool) or not isinstance(message_id, int):
            raise ValueError("message_id must be a number.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("message text must not be empty.")
        if not callable(reply_callback) or not callable(error_callback):
            raise ValueError("reply and error callbacks must be callable.")

        state = self._get_state(session_id)
        should_start = False

        with state.lock:
            state.pending_messages.append((message_id, text.strip()))
            state.revision += 1
            state.reply_callback = reply_callback
            state.error_callback = error_callback

            if not state.running:
                state.running = True
                should_start = True

            pending_count = len(state.pending_messages)

        logger.info(
            "📥 Message queued | session=%s pending=%d worker_started=%s",
            session_id,
            pending_count,
            should_start,
        )

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

        logger.info("🧹 Session reset | session=%s", session_id)

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
        pending = []
        stage = "generate"
        delivered = False
        try:
            while True:
                self.sleep_fn(self.debounce_seconds)

                with state.lock:
                    if not state.pending_messages:
                        state.running = False
                        return

                    pending = list(state.pending_messages)
                    state.pending_messages.clear()
                    revision = state.revision
                    generation = state.generation
                    reply_callback = state.reply_callback

                restarted = False

                while True:
                    combined_text = "\n".join(text for _message_id, text in pending)
                    in_reply_to_message_id = pending[0][0]
                    started_at = time.monotonic()
                    logger.info(
                        "⏳ Reply generation started | session=%s messages=%d chars=%d",
                        session_id,
                        len(pending),
                        len(combined_text),
                    )
                    reply = self.generate_reply(
                        session_id,
                        combined_text,
                        in_reply_to_message_id,
                    )
                    duration_ms = round((time.monotonic() - started_at) * 1000)
                    logger.info(
                        "✅ Reply generated | session=%s duration_ms=%d",
                        session_id,
                        duration_ms,
                    )

                    with state.lock:
                        if state.generation != generation:
                            break

                        has_new_messages = (
                            state.revision != revision and state.pending_messages
                        )
                        if has_new_messages and not restarted:
                            pending.extend(state.pending_messages)
                            state.pending_messages.clear()
                            revision = state.revision
                            reply_callback = state.reply_callback
                            restarted = True
                            logger.info(
                                "🔁 Reply superseded by a newer message | session=%s",
                                session_id,
                            )
                            continue

                        stage = "save"
                        saved_model_id = self.save_reply(session_id, reply)

                    logger.info(
                        "💾 Reply saved | session=%s",
                        session_id,
                    )

                    stage = "deliver"
                    reply_callback(reply)
                    delivered = True

                    if self.mark_messages_status is not None:
                        self._mark_safely(
                            session_id,
                            self._turn_message_ids(pending, saved_model_id),
                            "DELIVERED",
                        )
                    break

                with state.lock:
                    if not state.pending_messages:
                        state.running = False
                        return
        except Exception as error:
            logger.exception(
                "❌ Session processing failed | session=%s error_type=%s",
                session_id,
                type(error).__name__,
            )
            if pending and not delivered and self.mark_messages_status is not None:
                self._mark_safely(
                    session_id,
                    self._turn_message_ids(pending, saved_model_id if stage == "deliver" else None),
                    FAILURE_STATUS_BY_STAGE[stage],
                )
            with state.lock:
                error_callback = state.error_callback
                state.pending_messages.clear()
                state.running = False

            if error_callback is not None:
                error_callback(error)

    @staticmethod
    def _turn_message_ids(pending, saved_model_id):
        message_ids = [message_id for message_id, _text in pending]
        if saved_model_id is not None:
            message_ids.append(saved_model_id)
        return message_ids

    def _mark_safely(self, session_id, message_ids, status):
        try:
            self.mark_messages_status(session_id, message_ids, status)
        except Exception:
            logger.exception(
                "⚠️ Could not update message statuses | session=%s status=%s",
                session_id,
                status,
            )
