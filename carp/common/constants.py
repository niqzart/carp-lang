INPUT_ADDRESS: int = 1
# A memory address, mapped to the input device
OUTPUT_ADDRESS: int = 3
# A memory address, mapped to the output device

IO_DEVICE_COUNT: int = 16

WORD_LENGTH: int = 32
WORD_MAIN: int = 2 ** (WORD_LENGTH - 1)
WORD_MAX_VALUE: int = WORD_MAIN - 1
WORD_MIN_VALUE: int = -WORD_MAIN
