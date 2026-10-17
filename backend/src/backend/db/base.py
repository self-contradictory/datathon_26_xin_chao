from abc import ABC, abstractmethod
from contextlib import AbstractContextManager


class Database[ConnectionT](ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def connect(self) -> AbstractContextManager[ConnectionT]: ...
