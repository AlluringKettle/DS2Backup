from __future__ import annotations

import os
import shlex
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import *

#####################
# === Constants === #
#####################

TIME_DISPLAY_FORMAT = r'%Y/%m/%d %H:%M:%S'
TIME_FILE_FORMAT = r'%y%m%d%H%M%S'
SAVE_FILE_SUFFIX = r'.sl2'


###################
# === Utility === #
###################

def gen_save_file_path() -> Path:
    glob_iter = Path(os.environ['APPDATA']).joinpath('DarkSoulsII').rglob('*.sl2')
    return next(glob_iter)


def gen_backup_dir_path() -> Path:
    return Path('files')


def copy_file(src: Path, dst: Path) -> None:
    shutil.copy(str(src), str(dst))


def delete_file(src: Path) -> None:
    src.unlink()


class UnknownModeError(Exception):
    pass


class BackupNotFoundError(Exception):
    pass


################
# === Main === #
################

class Backup:
    __slots__ = ('path',)

    def __init__(self, path: Path) -> None:
        self.path = path
        self.check()

    def __str__(self) -> str:
        return self.name

    def check(self) -> None:
        if self.path.exists() and not self.path.is_file():
            raise IsADirectoryError(self.path)
        _ = self.time

    @property
    def name(self) -> str:
        return self.path.stem.partition('-')[2]

    @property
    def time(self) -> datetime:
        return datetime.strptime(self.path.stem.partition('-')[0], TIME_FILE_FORMAT)

    def save(self, save_file: SaveFile) -> None:
        copy_file(save_file.path, self.path)

    def load(self, save_file: SaveFile) -> None:
        copy_file(self.path, save_file.path)

    def delete(self) -> None:
        delete_file(self.path)


class BackupDir:
    __slots__ = ('path',)

    def __init__(self, path: Path) -> None:
        path.mkdir(exist_ok=True)
        self.path = path

    def __str__(self) -> str:
        return str(self.path.resolve())

    @property
    def backups(self) -> Iterable[Backup]:
        for file in self.path.glob(f'*{SAVE_FILE_SUFFIX}'):
            try:
                backup = Backup(file)
            except ValueError:
                break
            yield backup

    def find(self, selector: str = '') -> Backup:
        backup = ind_match = str_match = None
        for ind, backup in enumerate(self.backups, 1):
            if str(ind) == selector:
                ind_match = backup
            if str(backup) == selector:
                str_match = backup
        if not selector and backup:
            return backup
        elif selector and ind_match:
            return ind_match
        elif selector and str_match:
            return str_match
        raise BackupNotFoundError(selector)

    def create(self, name: str = None, time: datetime = None) -> Backup:
        name = name or ''
        time = time or datetime.now()
        time_str = time.strftime(TIME_FILE_FORMAT)
        path = self.path.joinpath(time_str + ('-' if name else '') + name + SAVE_FILE_SUFFIX)
        return Backup(path)


class SaveFile:
    __slots__ = ('path',)

    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(path)
        self.path = path

    def __str__(self) -> str:
        return str(self.path)


class Command:
    __slots__ = ('aliases', 'fun')

    commands: List[Command] = []

    def __init__(self, *aliases: str) -> None:
        self.aliases = aliases

    def __call__(self, fun: Callable) -> Callable:
        self.fun = fun
        type(self).commands.append(self)
        return fun

    def __repr__(self):
        return f'{type(self).__name__}{self.aliases!r}'


class CommandHandler:
    __slots__ = ('save_file', 'backup_dir', 'running')

    commands = Command.commands

    def __init__(self, save_file: SaveFile, backup_dir: BackupDir) -> None:
        self.running = None
        self.save_file = save_file
        self.backup_dir = backup_dir

    @Command('list', 'ls')
    def list(self) -> str:
        fstring = '{: >3.3} {: ^19.19}    {: <32.32}'
        backups = tuple(enumerate(self.backup_dir.backups, 1))
        if not backups:
            return 'No backups found'
        return '\n'.join((
            fstring.format('Num', 'Creation time', 'Name'),
            fstring.format(*('_' * 100,) * 4),
            *(fstring.format(f'{i}.', backup.time.strftime(TIME_DISPLAY_FORMAT), backup.name) for i, backup in backups),
        ))

    @Command('save')
    def save(self, selector='') -> str:
        backup = self.backup_dir.create(selector)
        backup.save(self.save_file)
        return f'Saved backup {backup}'

    @Command('load')
    def load(self, selector='') -> str:
        backup = self.backup_dir.find(selector)
        backup.load(self.save_file)
        return f'Loaded backup {backup}'

    @Command('delete', 'del')
    def delete(self, selector='') -> str:
        backup = self.backup_dir.find(selector)
        backup.delete()
        return f'Deleted backup {backup}'

    @Command('quit', 'q')
    def quit(self) -> str:
        self.running = False
        return 'Quitting...'

    def execute(self, cmd: str = '', *args: str) -> str:
        for command in self.commands:
            if cmd in command.aliases:
                return command.fun(self, *args)
        raise UnknownModeError(cmd)

    def execute_safe(self, argv: List[str]) -> str:
        try:
            return self.execute(*argv)
        except Exception as err:
            return ': '.join((type(err).__name__, *map(str, err.args)))

    def loop(self, inp_func: Callable, out_func: Callable) -> None:
        print("save / load / delete / quit")
        self.running = True
        while self.running:
            inp = shlex.split(inp_func())
            res = self.execute_safe(inp)
            out_func(res)


###################
# === Startup === #
###################

def main():
    
    save_file = SaveFile(gen_save_file_path())
    backup_dir = BackupDir(gen_backup_dir_path())
    cmd_handler = CommandHandler(save_file, backup_dir)
    if sys.argv[1:]:
        print(cmd_handler.execute_safe(sys.argv[1:]))
    else:
        cmd_handler.loop(input, print)


if __name__ == '__main__':
    main()
