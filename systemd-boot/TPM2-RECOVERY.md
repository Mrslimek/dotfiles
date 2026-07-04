# TPM2 + LUKS: восстановление авторазблокировки

Диск расшифровывается автоматически через TPM2, **пока** состояние системы
совпадает с тем, что было при enroll. Если что-то изменилось — TPM перестаёт
отдавать ключ, и при загрузке запрашивается **пароль LUKS** (это нормально,
не паникуй — это защита).

## Когда потребуется re-enroll

PCR 0 и PCR 7 изменились, если:

- **Обновился BIOS/UEFI** (PCR 0 — firmware state)
- **Изменились Secure Boot keys** (PCR 7): например, `sbctl enroll-keys` заново
- **Переключался Secure Boot** в BIOS (on → off → on меняет PCR 7)
- **Изменилась конфигурация Secure Boot** через `bootctl`

## Как понять, что нужен re-enroll

Симптом: при загрузке система запрашивает пароль LUKS, хотя раньше грузилась
без запроса. В dmesg/boot логе может быть упоминание TPM.

## Команда re-enroll

```bash
# 1. Загрузись с вводом пароля (как обычно)
# 2. Удали старый TPM-слот и создай новый с актуальными PCR:
sudo systemd-cryptenroll --wipe-slot=tpm2 \
    --tpm2-device=auto \
    --tpm2-pcrs=0+7 \
    /dev/nvme0n1p2
```

Система попросит текущий пароль LUKS для авторизации. После успешного
выполнения — при следующей перезагрузке диск снова разблокируется через TPM.

## Если вообще не работает TPM

Полная пересборка enrollment:

```bash
# Сначала удалить все TPM-слоты
sudo systemd-cryptenroll --wipe-slot=tpm2 /dev/nvme0n1p2

# Потом создать заново
sudo systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=0+7 /dev/nvme0n1p2
```

## Состояние LUKS-слотов (для проверки)

```bash
sudo cryptsetup luksDump /dev/nvme0n1p2 | grep -A1 'Keyslots'
```

Должно быть:
- `0: luks2` — пароль (резервный, **никогда не удаляй**)
- `1: luks2` — TPM-ключ

## Бэкап заголовка LUKS

При начальной настройке был создан `luks-header-backup.img`. Если заголовок
повредится — этот файл позволяет восстановить доступ. Хранить вне диска
(флешка, облако). Без него при повреждении заголовка — **данные потеряны**.

Создать свежий бэкап:
```bash
sudo cryptsetup luksHeaderBackup /dev/nvme0n1p2 \
    --header-backup-file /tmp/luks-header-backup.img
```

## Структура защиты

```
                ┌─ PCR 0 (firmware) ──────── BIOS не менялся ────┐
   TPM2 checks ─┤                                                    ├─→ отдаёт ключ
                └─ PCR 7 (Secure Boot) ─ SB keys не менялись ──────┘     ↓
                                                                       LUKS slot 1
                                                                            ↓
                                                                    диск открыт
```

Если любой PCR не совпал → TPM молчит → система просит пароль → LUKS slot 0.
