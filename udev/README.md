# udev hwdb — отключение физических навигационных клавиш

Здесь хранится hwdb-правило, отключающее физические **Home/End/PgUp/PgDn**
на встроенной клавиатуре ноутбука (AT Translated Set 2). Навигация при
этом остаётся доступной через Super+стрелки — см. [`keyd/`](../keyd/).

## Структура

```
udev/
├── README.md
└── etc/udev/hwdb.d/90-disable-keys.hwdb   → /etc/udev/hwdb.d/90-disable-keys.hwdb
```

> Каталог `/etc/udev/hwdb.d/` принадлежит пакету `systemd`, файл —
> пользовательский.

## Применение на новой системе

```bash
sudo stow --target=/ udev
sudo systemd-hwdb update
sudo udevadm trigger
```

Изменения вступают в силу без перезагрузки.

## На текущей системе (файл уже существует как обычный)

```bash
sudo stow --adopt --target=/ udev
sudo systemd-hwdb update
sudo udevadm trigger
```

либо вручную:

```bash
sudo rm /etc/udev/hwdb.d/90-disable-keys.hwdb
sudo stow --target=/ udev
sudo systemd-hwdb update
sudo udevadm trigger
```

## Синхронизация

**Из системы → в dotfiles:**

```bash
cp /etc/udev/hwdb.d/90-disable-keys.hwdb ~/dotfiles/udev/etc/udev/hwdb.d/90-disable-keys.hwdb
```

**Из dotfiles → в систему** (после правки в репо):

```bash
sudo systemd-hwdb update && sudo udevadm trigger
```

## Что внутри

`90-disable-keys.hwdb` матчит встроенную клавиатуру по modalias
`evdev:input:b0011v0001p0001*` и переназначает 4 сканкода в `reserved`
(клавиша отключается):

| Scancode | Клавиша |
|----------|---------|
| c7       | Home    |
| cf       | End     |
| c9       | PageUp  |
| d1       | PageDown|

## ⚠️ Привязка к модели клавиатуры

Modalias `b0011v0001p0001` — это стандартная **AT Translated Set 2
keyboard**, она встречается почти на всех ноутбуках. Но на другой машине
(другой ноут / внешняя клавиатура) правило может не сматчиться. Перед
применением на новом железе проверь modalias своей клавиатуры:

```bash
# Найти event-устройство встроенной клавиатуры
cat /proc/bus/input/devices | grep -A6 'AT Translated Set'

# Посмотреть её modalias (подставь свой eventN)
cat /sys/class/input/event4/device/modalias
```

Если modalias отличается — обнови строку `evdev:input:...` в hwdb-файле.
