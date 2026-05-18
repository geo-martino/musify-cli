from abc import abstractmethod

from mytunes_cli.operations import Operation


# noinspection PyAbstractClass
class ReportOperation[T](Operation):
    async def run(self) -> None:
        results = self._get_results()
        if results:
            self._log_results(results)

    @abstractmethod
    def _get_results(self, *args, **kwargs) -> dict[str, T]:
        raise NotImplementedError

    @abstractmethod
    def _log_results(self, results: dict[str, T]) -> None:
        raise NotImplementedError

    @staticmethod
    def _add_result_by_name(name: str, result: T, results: dict[str, T]) -> None:
        if not result:
            return

        if name in results:  # handle duplicate names
            count = sum(key.startswith(name) for key in results.keys())
            name += f" {count}"

        results[name] = result
