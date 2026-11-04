# Реестр методов — индекс

Индекс генерируется `tools/registry_scan.py`; вручную не редактировать.
Карточки методов исходного файла — в `registry/<ветвь>/<файл>.md`.

## [T0] t0.infra.registry — методов: 48

- [tools/check_limits.py](t0.infra.registry/check_limits.md) — Проверка лимита строк: каждый файл репозитория не длиннее 500 строк. — методов: 3
- [tools/registry_scan.py](t0.infra.registry/registry_scan.md) — Генератор реестра методов: индекс registry/METHODS.md и карточки по исходным файлам registry/<ветвь>/<файл>.md. Режим --check сверяет реестр без записи. — методов: 20
- [tests/test_registry_scan.py](t0.infra.registry/test_registry_scan.md) — Тесты генератора реестра: разбор аннотаций, план карточек по исходным файлам, рендер, сверка и очистка на диске. — методов: 25

## [T0] t0.infra.tests — методов: 0

- [tests/__init__.py](t0.infra.tests/__init__.md) — Пакет тестов: делает каталог tests импортируемым для unittest. — методов: 0

## [T0] t0.uvm.core — методов: 42

- [tools/uvm_core.py](t0.uvm.core/uvm_core.md) — Ядро UVM: состояние машины, ловушки, ОЗУ и стеки DS/RS (SPEC/L0-UVM.txt, Этап 1). — методов: 16
- [tests/test_uvm_core.py](t0.uvm.core/test_uvm_core.md) — Тесты ядра UVM: слова, ловушки, ОЗУ, стеки DS/RS и загрузка образа. — методов: 26

**Всего методов: 90**
