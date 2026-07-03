#!/bin/bash
#
# pkglist-sync.sh — регенерирует списки явно установленных пакетов в dotfiles.
# Вызывается pacman hook'ом (PostTransaction) после установки/удаления/обновления.
#
# Hook выполняется от root, поэтому скрипт сам определяет "настоящего" пользователя
# (через SUDO_USER / logname) и регенерирует файлы от его имени — чтобы они
# принадлежали пользователю, а не root, и были готовы к git commit.
#
# Генерируются два файла в ~/dotfiles:
#   pkglist.txt  — pacman -Qqe  (явно установленные пакеты, без зависимостей)
#   aurlist.txt  — pacman -Qqm  (foreign пакеты — обычно AUR)
#
# Атомарная запись через временный файл + mv, чтобы при сбое не осталось
# половины файла. Tихий при успехе — hook не должен засорять вывод pacman.

set -euo pipefail

# --- Определяем целевого пользователя (не root) -----------------------------
# При вызове `sudo pacman -S foo` hook бежит от root, но $SUDO_USER=viktor.
# Если SUDO_USER пуст (например вызов через pkexec/scripts), берём logname.
TARGET_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "")}"
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = "root" ]; then
    # Не смогли определить пользователя — молча выходим, это не авария.
    # Лучше пропустить обновление, чем записать файлы от root.
    exit 0
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f7 >/dev/null 2>&1 && getent passwd "$TARGET_USER" | cut -d: -f6 || echo "")
if [ -z "$TARGET_HOME" ] || [ ! -d "$TARGET_HOME" ]; then
    exit 0
fi

DOTFILES_DIR="$TARGET_HOME/dotfiles"
if [ ! -d "$DOTFILES_DIR/.git" ] && [ ! -f "$DOTFILES_DIR/.git" ]; then
    # dotfiles-репозиторий не найден — ничего не делаем.
    exit 0
fi

# --- Регенерация от имени пользователя ---------------------------------------
# Запускаем блок через sudo -u, чтобы:
#   1) pacman -Qq* читал БД пакетов корректно (она world-readable, но для чистоты)
#   2) файлы записались с владельцем $TARGET_USER, а не root
#   3) git впоследствии не ругался на чужие файлы
sudo -u "$TARGET_USER" bash -c '
    set -euo pipefail
    DOTFILES_DIR="'"$DOTFILES_DIR"'"

    # pkglist.txt — явно установленные (top-level), отсортировано.
    # -Q  query, -q  quiet (только имена), -e  explicit (явно установленные).
    tmp_pkgs=$(mktemp)
    pacman -Qqe | sort > "$tmp_pkgs"
    mv "$tmp_pkgs" "$DOTFILES_DIR/pkglist.txt"

    # aurlist.txt — foreign пакеты (не из синхронизируемых репо = обычно AUR).
    # -m  foreign.
    tmp_aur=$(mktemp)
    pacman -Qqm | sort > "$tmp_aur"
    mv "$tmp_aur" "$DOTFILES_DIR/aurlist.txt"
' || {
    # Если что-то пошло не так — сообщаем в stderr, но не ломаем транзакцию pacman.
    echo "pkglist-sync: WARNING — не удалось обновить списки пакетов" >&2
    exit 0
}

exit 0
