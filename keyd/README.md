# keyd — ремап клавиш на уровне ядра

`keyd` — системный демон переназначения клавиш. Здесь хранится конфиг,
который добавляет навигационные клавиши (Home/End/PgUp/PgDn) через
модификатор **Super**.

Работает в связке с [`udev/`](../udev/) — там физические навигационные
клавиши отключаются, а здесь те же функции возвращаются через Super+стрелки.

## Структура

```
keyd/
├── README.md
└── etc/keyd/default.conf   → /etc/keyd/default.conf
```

> Каталог `/etc/keyd/` создаётся пакетом `keyd`, а сам `default.conf` —
> пользовательский файл, пакету не принадлежит.

## Применение на новой системе

Пакет `keyd` уже есть в `pkglist.txt`. После установки:

```bash
sudo stow --target=/ keyd
sudo systemctl enable --now keyd
```

## На текущей системе (файл уже существует как обычный)

Если `/etc/keyd/default.conf` уже лежит обычным файлом (не симлинком),
`stow` откажется его перезаписывать. Два варианта:

```bash
# 1) --adopt: заменит обычный файл на симлинк и заберёт его содержимое в репо
sudo stow --adopt --target=/ keyd

# 2) вручную: удалить старый, затем стовать
sudo rm /etc/keyd/default.conf
sudo stow --target=/ keyd
```

## Синхронизация

**Из системы → в dotfiles** (правил прямо в `/etc`):

```bash
cp /etc/keyd/default.conf ~/dotfiles/keyd/etc/keyd/default.conf
```

**Из dotfiles → в систему** (после правки в репо):

```bash
sudo systemctl restart keyd
```

## Что внутри

`default.conf` применяется ко всем устройствам (`[ids] *`). В секции
`[meta]` (зажатый Super):

| Комбинация     | Результат |
|----------------|-----------|
| Super + ←      | Home      |
| Super + →      | End       |
| Super + ↑      | PageUp    |
| Super + ↓      | PageDown  |
