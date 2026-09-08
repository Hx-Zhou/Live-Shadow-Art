from dataclasses import dataclass, field
from time import perf_counter


@dataclass
class PerformanceRecord:
  provider: str
  task_id: str
  started_at: float = field(default_factory=perf_counter)
  finished_at: float | None = None
  success: bool = False

  def finish(self, success: bool) -> None:
    self.finished_at = perf_counter()
    self.success = success

  @property
  def duration_ms(self) -> float | None:
    if self.finished_at is None:
      return None
    return (self.finished_at - self.started_at) * 1000
