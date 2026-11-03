# Реестр методов — индекс

Индекс генерируется `tools/registry_scan.py`; вручную не редактировать.
Карточки методов ветви — в `registry/<ветвь>.md`.

## [T0] t0.infra.registry — методов: 38

- tools/check_limits.py — Проверка лимита строк: каждый файл репозитория не длиннее 500 строк.
- tools/registry_scan.py — Генератор реестра методов: индекс registry/METHODS.md и карточки ветвей registry/<ветвь>.md. Режим --check сверяет реестр без записи.
- tests/test_registry_scan.py — Тесты генератора реестра: разбор аннотаций, группировка, рендер.
- карточки: `registry/t0.infra.registry.md`

## [T0] t0.infra.tests — методов: 0

- tests/__init__.py — Пакет тестов: делает каталог tests импортируемым для unittest.
- карточки: `registry/t0.infra.tests.md`

## [T0] t0.uvm.core — методов: 16

- tools/uvm_core.py — Ядро UVM: состояние машины, ловушки, ОЗУ и стеки DS/RS (SPEC/L0-UVM.md, Этап 1).
- карточки: `registry/t0.uvm.core.md`

**Всего методов: 54**
