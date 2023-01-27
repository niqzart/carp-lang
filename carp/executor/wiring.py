from common.constants import INPUT_ADDRESS, OUTPUT_ADDRESS, IO_DEVICE_COUNT
from common.operations import Operation, Registry
from executor.alu import ALU, ALUOperation
from executor.logs import LogRecord, RegistriesRecord, FlagsRecord


class DataPath:
    """
    All passive elements of the processor are simulated within this class.
    It includes: registries, memory and the ALU.
    Methods simulate processor's inner workings
    """

    def __init__(
        self,
        data_memory_size: int,
        instruction_memory: list[Operation],
        input_data: list[int],
    ) -> None:
        self.general_registries: dict[Registry.Code, int] = {
            Registry.Code.ACCUMULATOR: 0,
            Registry.Code.BUFFER: 0,
        }
        self.alu = ALU()

        self.data_memory: list[int] = [0 for _ in range(data_memory_size)]
        self.memory_pointer: int = 0
        self.stack_pointer: int = data_memory_size

        self.instruction_memory: list[Operation] = instruction_memory
        self.instruction_pointer: int = 0
        self.command_data: Operation | None = None

        self.io: dict[int, list[int]] = {
            INPUT_ADDRESS: input_data[::-1],
            OUTPUT_ADDRESS: [],
        }
        self.last_io: dict[int, int | None] = {}

    @property
    def accumulator(self) -> int:
        return self.general_registries[Registry.Code.ACCUMULATOR]

    @property
    def buffer(self) -> int:
        return self.general_registries[Registry.Code.BUFFER]

    def read_command(self) -> bool:
        """
        Read from the instruction memory if there are any commands left.
        Uses :py:attr:`instruction_pointer` as the address.
        """
        if self.instruction_pointer >= len(self.instruction_memory):
            return False
        self.command_data = self.instruction_memory[self.instruction_pointer]
        return True

    def _get_io_device(self, index: int) -> list[int]:
        device = self.io.get(index)
        if device is None:
            raise RuntimeError(f"Device {index} not connected")
        return device

    def memory_read(self, destination: Registry.Code, stack: bool = False) -> None:
        """
        Reads from the data memory to a specified general registry.
        Uses :py:attr:`memory_pointer` or :py:attr:`stack_pointer` as the address.
        The memory-mapped input is also *imitated* here.
        """
        index = self.stack_pointer - 1 if stack else self.memory_pointer
        if 0 <= index < IO_DEVICE_COUNT:
            device = self._get_io_device(index)
            data = 0 if len(device) == 0 else device.pop()
            self.last_io[index] = data
        elif IO_DEVICE_COUNT <= index < len(self.data_memory):
            data = self.data_memory[index]
        else:
            raise IndexError("An attempt to read from outside the memory")
        self.general_registries[destination] = self.alu_execute(
            operation=ALUOperation.LEFT,
            left=data,
            right=0,
        )

    def memory_write(self, source: Registry.Code, stack: bool = False) -> None:
        """
        Write data from the specified general registry to data memory.
        Uses :py:attr:`memory_pointer` or :py:attr:`stack_pointer` as the address.
        The memory-mapped output is also *imitated* here.
        """
        data = self.general_registries[source]
        index = self.stack_pointer if stack else self.memory_pointer
        if 0 <= index < IO_DEVICE_COUNT:
            self._get_io_device(index).append(data)
            self.last_io[index] = data
        elif IO_DEVICE_COUNT <= index < len(self.data_memory):
            self.data_memory[index] = data
        else:
            raise IndexError("An attempt to write to outside the memory")

    def alu_execute(
        self,
        operation: ALUOperation,
        left: int,
        right: int,
        flags: bool = True,
    ) -> int:
        """
        Sends operations to the ALU. Numbers should come from registers and the
        result should be discarded or written to a registry.
        This also sets Zero and Negative flags unless `flags=True` is passed.
        """
        self.alu.left = left
        self.alu.right = right
        self.alu.execute(operation, flags=flags)
        return self.alu.result

    def record_state(self) -> LogRecord:
        """Logging/debugging function to record the full state of the DataPath"""
        self.last_io = {}
        return LogRecord(
            registries=RegistriesRecord(
                accumulator=self.accumulator,
                buffer=self.buffer,
                memory_pointer=self.memory_pointer,
                stack_pointer=self.stack_pointer,
                instruction_pointer=self.instruction_pointer,
                command_data=self.command_data,
            ),
            flags=FlagsRecord(
                zero=self.alu.zero,
                negative=self.alu.negative,
            ),
            input_data=self.last_io.get(INPUT_ADDRESS),
            output_data=self.last_io.get(OUTPUT_ADDRESS),
        )

    def get_output(self) -> list[int]:
        """A simplification function for getting full program's standard output"""
        return self.io[OUTPUT_ADDRESS]
