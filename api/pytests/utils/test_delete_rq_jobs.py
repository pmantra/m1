from unittest.mock import Mock

from utils.delete_rq_jobs import DeleteRQJobs


class TestDeleteRQJobs:
    def test_deleting_jobs(self, mock_queue):
        # Given
        func_name = "my_rq_func"
        job_mock = Mock()
        job_mock.func_name = func_name
        mock_queue.get_jobs.return_value = [job_mock]
        rq_deleter = DeleteRQJobs(
            queue=mock_queue, queue_name="test", func_name=func_name, page_limit=1
        )

        # When
        rq_deleter.delete_jobs()
        # Then
        assert job_mock.delete.called is True
