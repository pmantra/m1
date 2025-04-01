from unittest.mock import MagicMock, call, patch

import pytest

from tracks.lifecycle_events.event_system import (
    EventType,
    dispatch_initiate_event,
    dispatch_terminate_event,
    dispatch_transition_event,
    event_handler,
    event_manager,
    execute_handler,
    handler_registry,
)


class TestEventManager:
    @pytest.fixture
    def reset_event_manager(self):
        original_handlers = event_manager._handlers.copy()
        event_manager._handlers = {}

        yield

        event_manager._handlers = original_handlers

    @pytest.fixture
    def reset_handler_registry(self):
        original_registry = handler_registry.copy()
        handler_registry.clear()

        yield

        handler_registry.update(original_registry)

    def test_register_handler(self, reset_event_manager):
        def test_handler(track, user):
            pass

        event_manager.register(EventType.INITIATE, test_handler)

        assert len(event_manager._handlers) == 1
        assert EventType.INITIATE.value in event_manager._handlers
        assert len(event_manager._handlers[EventType.INITIATE.value]) == 1
        assert event_manager._handlers[EventType.INITIATE.value][0] == test_handler

    def test_register_multiple_handlers(self, reset_event_manager):
        def handler1(track, user):
            pass

        def handler2(track, user):
            pass

        event_manager.register(EventType.INITIATE, handler1)
        event_manager.register(EventType.INITIATE, handler2)

        assert len(event_manager._handlers[EventType.INITIATE.value]) == 2
        assert handler1 in event_manager._handlers[EventType.INITIATE.value]
        assert handler2 in event_manager._handlers[EventType.INITIATE.value]

    def test_register_different_event_types(self, reset_event_manager):
        def initiate_handler(track, user):
            pass

        def terminate_handler(track, user):
            pass

        event_manager.register(EventType.INITIATE, initiate_handler)
        event_manager.register(EventType.TERMINATE, terminate_handler)

        assert len(event_manager._handlers) == 2
        assert EventType.INITIATE.value in event_manager._handlers
        assert EventType.TERMINATE.value in event_manager._handlers
        assert event_manager._handlers[EventType.INITIATE.value][0] == initiate_handler
        assert (
            event_manager._handlers[EventType.TERMINATE.value][0] == terminate_handler
        )

    @patch("tracks.lifecycle_events.event_system.execute_handler")
    def test_dispatch_event(self, mock_execute_handler, reset_event_manager):
        def test_handler(track, user):
            pass

        event_manager.register(EventType.INITIATE, test_handler)

        mock_track = MagicMock()
        mock_user = MagicMock()
        event_manager.dispatch(EventType.INITIATE, track=mock_track, user=mock_user)

        mock_execute_handler.delay.assert_called_once_with(
            test_handler.__name__,
            EventType.INITIATE.value,
            track=mock_track,
            user=mock_user,
        )

    @patch("tracks.lifecycle_events.event_system.execute_handler")
    def test_dispatch_multiple_handlers(
        self, mock_execute_handler, reset_event_manager
    ):
        def handler1(track, user):
            pass

        def handler2(track, user):
            pass

        event_manager.register(EventType.INITIATE, handler1)
        event_manager.register(EventType.INITIATE, handler2)

        mock_track = MagicMock()
        mock_user = MagicMock()
        event_manager.dispatch(EventType.INITIATE, track=mock_track, user=mock_user)

        mock_execute_handler.delay.assert_has_calls(
            [
                call(
                    handler1.__name__,
                    EventType.INITIATE.value,
                    track=mock_track,
                    user=mock_user,
                ),
                call(
                    handler2.__name__,
                    EventType.INITIATE.value,
                    track=mock_track,
                    user=mock_user,
                ),
            ]
        )
        assert mock_execute_handler.delay.call_count == 2

    @patch("tracks.lifecycle_events.event_system.execute_handler")
    def test_dispatch_no_handlers(self, mock_execute_handler, reset_event_manager):
        mock_track = MagicMock()
        mock_user = MagicMock()
        event_manager.dispatch(EventType.INITIATE, track=mock_track, user=mock_user)

        mock_execute_handler.delay.assert_not_called()


class TestEventHandler:
    @pytest.fixture
    def reset_event_manager(self):
        original_handlers = event_manager._handlers.copy()
        event_manager._handlers = {}

        yield

        event_manager._handlers = original_handlers

    @pytest.fixture
    def reset_handler_registry(self):
        original_registry = handler_registry.copy()
        handler_registry.clear()

        yield

        handler_registry.update(original_registry)

    def test_event_handler_decorator(self, reset_event_manager, reset_handler_registry):
        @event_handler(EventType.INITIATE)
        def test_handler(track, user):
            pass

        assert EventType.INITIATE.value in event_manager._handlers
        assert event_manager._handlers[EventType.INITIATE.value][0] == test_handler
        assert handler_registry[test_handler.__name__] == test_handler

    def test_multiple_event_handlers(self, reset_event_manager, reset_handler_registry):
        @event_handler(EventType.INITIATE)
        def handler1(track, user):
            pass

        @event_handler(EventType.INITIATE)
        def handler2(track, user):
            pass

        assert len(event_manager._handlers[EventType.INITIATE.value]) == 2
        assert handler1 in event_manager._handlers[EventType.INITIATE.value]
        assert handler2 in event_manager._handlers[EventType.INITIATE.value]
        assert handler_registry[handler1.__name__] == handler1
        assert handler_registry[handler2.__name__] == handler2


class TestExecuteHandler:
    @pytest.fixture
    def reset_handler_registry(self):
        original_registry = handler_registry.copy()
        handler_registry.clear()

        yield

        handler_registry.update(original_registry)

    @patch("tracks.lifecycle_events.event_system.logger")
    def test_execute_handler(self, mock_logger, reset_handler_registry):
        handler_mock = MagicMock()
        handler_registry["test_handler"] = handler_mock

        mock_track = MagicMock()
        mock_user = MagicMock()
        execute_handler(
            "test_handler", EventType.INITIATE.value, track=mock_track, user=mock_user
        )

        handler_mock.assert_called_once_with(track=mock_track, user=mock_user)
        mock_logger.info.assert_any_call(
            "Executing event handler",
            handler_name="test_handler",
            event_type=EventType.INITIATE.value,
        )
        mock_logger.info.assert_any_call(
            "Handler execution completed successfully",
            handler_name="test_handler",
            event_type=EventType.INITIATE.value,
        )

    @patch("tracks.lifecycle_events.event_system.logger")
    def test_execute_handler_not_found(self, mock_logger, reset_handler_registry):
        mock_track = MagicMock()
        mock_user = MagicMock()
        execute_handler(
            "nonexistent_handler",
            EventType.INITIATE.value,
            track=mock_track,
            user=mock_user,
        )

        mock_logger.error.assert_called_with(
            "Handler not found in registry",
            handler_name="nonexistent_handler",
            event_type=EventType.INITIATE.value,
        )

    @patch("tracks.lifecycle_events.event_system.logger")
    def test_execute_handler_exception(self, mock_logger, reset_handler_registry):
        def failing_handler(track, user):
            raise ValueError("Test error")

        handler_registry["failing_handler"] = failing_handler

        mock_track = MagicMock()
        mock_user = MagicMock()
        execute_handler(
            "failing_handler",
            EventType.INITIATE.value,
            track=mock_track,
            user=mock_user,
        )

        mock_logger.error.assert_called_with(
            "Error executing event handler",
            handler_name="failing_handler",
            event_type=EventType.INITIATE.value,
            error="Test error",
            exc_info=mock_logger.error.call_args.kwargs["exc_info"],
        )


class TestDispatchFunctions:
    @patch("tracks.lifecycle_events.event_system.event_manager")
    def test_dispatch_initiate_event(self, mock_event_manager):
        mock_track = MagicMock()
        mock_user = MagicMock()

        with patch("utils.transactional.manager.register") as mock_register:

            def execute_callback_immediately(func, *args, **kwargs):
                func(*args, **kwargs)

            mock_register.side_effect = execute_callback_immediately

            dispatch_initiate_event(mock_track, mock_user)

            mock_event_manager.dispatch.assert_called_once_with(
                EventType.INITIATE, track_id=mock_track.id, user_id=mock_user.id
            )

    @patch("tracks.lifecycle_events.event_system.event_manager")
    def test_dispatch_terminate_event(self, mock_event_manager):
        mock_track = MagicMock()
        mock_user = MagicMock()

        with patch("utils.transactional.manager.register") as mock_register:

            def execute_callback_immediately(func, *args, **kwargs):
                func(*args, **kwargs)

            mock_register.side_effect = execute_callback_immediately

            dispatch_terminate_event(mock_track, mock_user)

            mock_event_manager.dispatch.assert_called_once_with(
                EventType.TERMINATE, track_id=mock_track.id, user_id=mock_user.id
            )

    @patch("tracks.lifecycle_events.event_system.event_manager")
    def test_dispatch_transition_event(self, mock_event_manager):
        mock_source_track = MagicMock()
        mock_target_track = MagicMock()
        mock_user = MagicMock()

        with patch("utils.transactional.manager.register") as mock_register:

            def execute_callback_immediately(func, *args, **kwargs):
                func(*args, **kwargs)

            mock_register.side_effect = execute_callback_immediately

            dispatch_transition_event(mock_source_track, mock_target_track, mock_user)

            mock_event_manager.dispatch.assert_called_once_with(
                EventType.TRANSITION,
                source_track_id=mock_source_track.id,
                target_track_id=mock_target_track.id,
                user_id=mock_user.id,
            )
