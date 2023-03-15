# Лабораторная работа №3 по Архитектуре компьютера

- Нестеров Николай Константинович
- `lisp | risc | harv | hw | instr | struct | stream | mem | prob2`

## Язык программирования
CARP — Creative ARRay Processor

### BNF
```ebnf
<program> ::= <block>

<block> ::= <expression> | <expression> <s> <block>
<expression> ::= "(" <command> ")"

<command> ::= "output" <s> <arg> | 
              "print" <s> <arg> | 
              "print" <s> '"' <string> '"' |
              "assign" <s> <var> <s> <arg> |
              <construct> <s> <boolean> <s> <block>
 
<construct> ::= "if" | "loop"
<boolean> ::= "(" <comparator> <s> <arg> <s> <arg> ")" | <var>
<comparator> ::= "=" | ">" | "<" | ">=" | "<=" | "!="

<valuable> ::= "input" | <operand> <s> <args>
<args> ::= <arg> | <arg> <s> <args> 
<operand> ::= "+" | "-" | "*" | "/" | "%"

<arg> ::= <number> | <var> | <valuable>

<number> ::= r"-?[0-9]+"
<var> ::= r"[a-z_][a-z_0-9]*"
<s> ::= r"[ \t\n]+"
```

### Упрощения
- у выражений ограничено количество операндов
- вырезаны присвоения ("+=", "/=" и т.п.)
- оставлена только одна операция цикла (loop как while)
- нет функций и вложенных блоков

### Операции
|     код(ы)     |      аргументы      |                           описание                           |
|:--------------:|:-------------------:|:------------------------------------------------------------:|
| = > < >= <= != |    два аргумента    |         выполняет сравнение значений двух аргументов         |
|   + - * / %    | несколько аргумента | возвращает результат математической операции над аргументами |
|     input      |         нет         |    возвращает одно машинное слово пользовательского ввода    |
|     output     |      аргумент       |             выводит пользователю аргумент-число              |
|     print      |  аргумент / стока   |   выводит пользователю символ по коду аргумента или стоку    |
|     assign     | название + аргумент |   задаёт переменной значение по названию (может создавать)   |
|       if       |   условие + блок    |         выполняет блок, только если условие правдиво         |
|      loop      |   условие + блок    |            выполняет блок, пока условие правдиво             |

### Семантика
- Основная стратегия вычисления: вызов при упоминании – аргументы вычисляются перед вызовом функции / запуска оператора. Так как операндов максимум два, это не вызывает проблем с необходимостью аллоцировать память на промежуточные значения аргументов
- Функции в языке не реализованы, поэтому стратегии их вызова неактуальны
- Математические операции выполняются в том порядке, в котором заданы программистом. Нет мест, в которых порядок действий был неопределённым (невозможна ситуация вида: `a + b * c`, она будет записана как: `(+ a (* b c))` или `(* (+ a b) c)`)
- Область видимости одна, глобальная, необходимости делить области не было
- Для переменных существует один тип: число. Булевые значения появляются только в конструкции <condition> и не могут участвовать в операциях с другими типами
- Если думать широко, то типизация скорее будет динамической. При развитии языка явно понадобится сохранять булевые, строчные и другие значения в переменные
- Типизация строгая, преобразования типов не реализовано, но если когда-то будет, то будет требоваться в явном виде

## Организация памяти
### Работа с памятью
- I/O размаплено на память, первые 16 адресов зарезервированы под внешние устройства
- Констант в языке не реализовано за ненадобностью
- Переменные определяются в памяти данных, все они глобальные
- Место для переменных определяется на этапе компиляции
- Существует стек, помещённый в конец памяти данных

### Модель памяти
- Гарвардская архитектура: память инструкций отделена от памяти данных
- Только абсолютная адресация
- Машинное слово 32 бита, знаковое
- Пользователю доступны два регистра общего назначения: accumulator и buffer
- Пользователю доступен стек, управляемый дополнительным регистром SP (stack pointer)

### Отображение
```text
Instruction Memory
+---------------------+
| 00 : program start  | <- начало программы в начале памяти
|        .....        |
| i : 0               | <- конец программы это NULL
+---------------------+

Data Memory
+-----------------------+
| 00 : device           | <- memory-mapped i/o
| 01 : device           | <- main input
| 02 : device           |
| 03 : device           | <- main output
|        .....          |
| i+0 : variable        | <- global variables
| i+1 : variable        |
|        .....          |
| c+0 : stack top value | <- stack at the bottom
| c+1 : stack value     |
+-----------------------+
```

## Система команд
### Особенности процессора
- машинное слово 32-битное, знаковое
- ввод-вывод размаплен на память, запись в ячейки 0 - 15 обращается к внешним устройствам
- прерывания не реализованы за ненадобностью

#### Регистры
| код |      название       |        тип        |                      назначение                       |
|:---:|:-------------------:|:-----------------:|:-----------------------------------------------------:|
|  A  |     accumulator     | общего назначения |          участие в арифметических операциях           |
|  B  |       buffer        | общего назначения |          участие в арифметических операциях           |
| MP  |   memory pointer    |     адресный      |     хранит адрес памяти данных для операций с ней     |
| SP  |    stack pointer    |     адресный      |      хранит адрес вершины стека в памяти данных       |
| IP  | instruction pointer |     адресный      |     хранит адрес памяти команд следующей команды      |
| CD  |    command data     |      особый       |          хранит текущую исполняемую команду           |
|  Z  |      zero flag      |       флаг        |       был ли результат последнего вычисления 0?       |
|  N  |    negative flag    |       флаг        | был ли результат последнего вычисления отрицательным? |

### Набор инструкций
#### Работа с памятью
| название | аргумент1 | аргумент2 |               описание                |
|:--------:|:---------:|:---------:|:-------------------------------------:|
|   load   |  Регистр  |   Адрес   | Загружает данные из памяти в регистр  |
|   save   |  Регистр  |   Адрес   | Сохраняет данные из регистра в память |
|   grab   |  Регистр  |           | Достаёт элемент с вершину стека (pop) |
|   push   |  Регистр  |           |  Складывает элемент на вершину стека  |

#### Математические операции
| название | аргумент1 (A) |  аргумент2 (B)  |            результат             |
|:--------:|:-------------:|:---------------:|:--------------------------------:|
|   add    |    Регистр    | Регистр / Число |           `A = A + B`            |
|   sub    |    Регистр    | Регистр / Число |           `A = A - B`            |
|   mul    |    Регистр    | Регистр / Число |           `A = A * B`            |
|   div    |    Регистр    | Регистр / Число | `A = A / B` (только целая часть) |
|   mod    |    Регистр    | Регистр / Число |   `A = A / B`(только остаток)    |
|   cmp    |    Регистр    | Регистр / Число |    Выставить флаги по `A - B`    |
|   pmc    |    Регистр    | Регистр / Число |    Выставить флаги по `B - A`    |
|   mov    |    Регистр    | Регистр / Число |             `A = B`              |

#### Операции перехода
| название | аргумент1 | аргумент2 |               описание                |
|:--------:|:---------:|:---------:|:-------------------------------------:|
|    jz    |  Offset   |           |   Переход, если выставлен флаг Zero   |
|    jn    |  Offset   |           | Переход, если выставлен флаг Negative |
|    jb    |  Offset   |           |          Безусловный переход          |

Переходим на offset (целое число), причём так как переходы происходят после выборки команды зациклиться можно запустив `jb -1`

### Способ кодирования инструкций
- Сериализуются в список json-объектов
- Т.к. память инструкции отдельна, нумерация идёт с нуля
- Общая структура инструкции (полная [json-schema](./docs/operation-schema.json)):

```json5
{
  "code": "mov",  // строчной код инструкции из таблиц выше
  "left": {  // первый (левый) аргумент [работа с памятью или математика]
    "type": "registry",  // в виде регистра
    "code": "A"  // A или B
  },
  "right": {  // второй (правый) аргумент [только математические]
    "type": "value",  // в виде значения
    "code": 4000000,  // целое число
  },
  "address": 16,  // абсолютный адрес в памяти, к которому обращаются [только работа с памятью]
  "offset": -4,  // целое число-offset для перехода [только переходы]
}
```

## Транслятор
### Использование
```text
Usage: python -m carp translate [OPTIONS] INPUT_FILE [OUTPUT_PATH]

Arguments:
  INPUT_FILE     Path to the source file  [required]
  [OUTPUT_PATH]  Path for the output (leave empty to use <input>.curp)

Options:
  --save-parsed  Saves parsed symbols to a file as well           
  --help         Show this message and exit
```

### Этапы
1. Конвертирование файла в список Symbol ([`translator.parser`](./carp/translator/parser.py). Символ это строка без пробельных символов (такие символы в языке являются главными разделителями) или строка, завёрнутая в кавычки. Исходный файл преобразуется в символы путём разбора его посимвольно. Одновременно с конвертацией проверяются кавычки, и запоминаются расположения символов в исходном коде (для точных ошибок на этом и следующих этапах). Пример промежуточного результата работы этого этапа можно найти в папке [`examples`](./examples), с разрешением `.cpar`, например, [`prob2.cpar`](./examples/prob2.cpar)
2. Конвертирование символов в операции машинного кода ([`translator.translator`](./carp/translator/translator.py))). Транслятор через интерфейс читателя ([`translator.reader`](./carp/translator/reader.py)) выбирает символы и строит по ним машинный код, записывая инструкции в список. Затем эти инструкции сериализуются в json и записываются в output-файл. Примеры также можно найти в папке [`examples`](./examples), с разрешением `.curp`, например, [`prob2.curp`](./examples/prob2.curp)

### Прочее
- За регистрацию переменных отвечает модуль [`translator.variables`](./carp/translator/variables.py)
- Все операции и промежуточные конструкции хранятся в pydantic-моделях, что сильно помогает типизации и простоте модификации кода
- Структура Translator напоминает описание синтаксиса в BNF
- Ошибки синтаксиса выводятся в стандартный вывод, первая ошибка прекращает дальнейшую обработку файла
- Т.к. символы привязаны к месту в исходном коде, ошибка содержит достаточно дебаг-информации

## Модель процессора
### Использование
```text
Usage: python -m carp execute [OPTIONS] INSTRUCTIONS [INPUT_STRING] [OUTPUT_PATH]

Arguments:
  INSTRUCTIONS    Path to the compiled code file  [required]
  [INPUT_STRING]  Path for the input data
  [OUTPUT_PATH]   Path for the output data

Options:
  --save-log      Saves the execution logs to a file
  --help          Show this message and exit.
```

### Реализация
- арифметико-логическое устройство выделено в [`executor.alu`](./carp/executor/alu.py)
- структуры для ведения журнала (pydantic-модели) вынесены в [`executor.logs`](./carp/executor/logs.py)
- data-flow-модель для пассивного содержания все элементов процессора реализована в [`executor.wiring`](./carp/executor/wiring.py)
- control-unit, управляющий всеми циклами процессора, реализован в [`executor.control`](./carp/executor/control.py)

### Схема
<img src="./docs/processor-model.drawio.png"/>

### Циклы ControlUnit
- Instruction Fetch — получает текущую инструкцию, чтобы её выполнить
  - Читаем инструкцию в CD по IP
  - ControlUnit расшифровывает инструкцию
  - Увеличиваем IP на единицу
- Command Execute — вычисляет какое-то нужное команде значение
  - Для математических операций производится действие над регистрами
  - Для операций перехода из IP и CD вычисляется адрес, на который нужно перейти, и записывается в IP
  - Для операций работы с памятью в MP помещается адрес из CD
  - Для операций со стеком из SP и CD вычисляется новое значение SP
- Memory Fetch — читает или пишет в память, если команда того требует
  - Для чтения используется вычисленный ранее адрес
  - Чтение может производиться в любой регистр общего назначения

### Особенности
- Регистры описаны [ранее](#Набор-инструкций)
- Память инструкций хранит инструкции. Процессор выполняет их последовательно, кроме операций переходов, которые влияют на IP-регистр, меняя порядок выполнения
- Регистр команд используется в ControlUnit и может быть передан для адресации памяти в MP, а если команда содержит значение аргумента, CD можно направить на любой из входов АЛУ
- Кроме того, для адресации может использоваться SP-регистр, модифицируемый на цикле исполнения инструкции при необходимости. Приходить в АЛУ он может только через левый вход (другое не было нужно)
- Оба регистра общего назначения (A и B) могут получить результат вычисления с АЛУ, а также могут попасть на любой из его входов
- Регистры статуса Negative и Zero получаются из АЛУ и доступны ControlUnit-у
- Ввод/вывод размаплен на память

## Апробация
### Тесты
- Тесты написаны на pytest
- Unit-тесты, покрывающие все индивидуальные части ([translation](./carp/tests/translation) и [execution](./carp/tests/execution))
- Интеграционные тесты используют подготовленные команды и запускают проект также, как запускал бы пользователь ([integrational](./carp/tests/integrational))
- Интеграционные тесты используют golden-тестирование, обновить вывод: `pytest tests/integrational --update-goldens`
- Запустить все тесты (из папки `carp`): `pytest tests --cov=.`
- При прогоне также считается покрытие

### CI
- Настроен линтер flake8 с [кучей плагинов](./requirements-dev.txt)
- Настроен линтер isort
- Настроен mypy в строгом режиме (со всеми опциональными проверками)
- Настройки линтеров и coverage лежат в [setup.cfg](./setup.cfg)
- Все линтеры и тесты включены в [github-pipeline](./.github/workflows/main-check.yml)
- Используется написанный мной open-source [callable workflow](https://github.com/niqzart/ca-actions)

### Таблица трёх алгоритмов
|      ФИО      | алг.  | LoC | code инстр. | инстр. |
|:-------------:|:-----:|:---:|:-----------:|:------:|
| Нестеров Н.К. | hello |  1  |     22      |   23   |
| Нестеров Н.К. |  cat  |  6  |      9      |   11   |
| Нестеров Н.К. | prob2 | 13  |     28      |  568   |
| Нестеров Н.К. | many  |  1  |     27      |   48   |

### Реализация алгоритмов
Все файлы содержаться в папке [`examples`](./examples), с разрешениями `.carp`, `.curp` и `.clog` для исходников, машинного кода и журнала соответственно, можно попасть туда через таблицу ссылок:

| алг.  |              исходник               |              машинный               |               журнал                |
|:-----:|:-----------------------------------:|:-----------------------------------:|:-----------------------------------:|
| hello | [hello.carp](./examples/hello.carp) | [hello.curp](./examples/hello.curp) | [hello.clog](./examples/hello.clog) |
|  cat  |   [cat.carp](./examples/cat.carp)   |   [cat.curp](./examples/cat.curp)   |   [cat.clog](./examples/cat.clog)   |
| prob2 | [prob2.carp](./examples/prob2.carp) | [prob2.curp](./examples/prob2.curp) | [prob2.clog](./examples/prob2.clog) |
| many  |  [many.carp](./examples/many.carp)  |  [many.curp](./examples/many.curp)  |  [many.clog](./examples/many.clog)  |
