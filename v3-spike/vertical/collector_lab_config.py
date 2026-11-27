"""Explicit same-host LAB provisioning; not a physically independent witness.

Maintenance must cooperate with the local lock. Never restore these files
with the application DB or collector journal. No production authorization.
"""
from contextlib import closing, contextmanager
import fcntl
import os
from pathlib import Path
import secrets
import stat

from collector_admission_fence import initialize, provision, authenticated
from authority_restore_guard_candidate import open_existing, provision_witness, snapshot, distinct

SCOPE = ('synthetic-demo', 'NODE-CI-ROOT', 'COLLECTOR-lab')


def require(ok):
    if not ok:
        raise ValueError('unsafe LAB collector configuration')


def private_dir(path):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o077 and path.resolve(strict=True) == path)


def private_file(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o077 and info.st_nlink == 1
            and path.resolve(strict=True) == path)
    return info.st_dev, info.st_ino


def paths(root):
    root = Path(root)
    require(root.is_absolute() and root != Path('/') and root.resolve(strict=True) == root)
    info = root.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o022)
    return root / 'collector-control', root / 'collector-authority', root / 'collector-witness'


def exclusive_file(path, payload=b''):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(payload)
        out.flush()
        os.fsync(out.fileno())


@contextmanager
def maintenance_lock(control):
    private_dir(control)
    lock = control / 'maintenance.lock'
    identity = private_file(lock)
    fd = os.open(lock, os.O_NOFOLLOW | os.O_RDWR)
    active = False
    try:
        info = os.fstat(fd)
        require((info.st_dev, info.st_ino) == identity)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = True

        def permitted():
            try:
                return active and private_file(lock) == identity
            except (OSError, ValueError):
                return False

        yield permitted
    finally:
        active = False
        os.close(fd)


def provision_new(root):
    """Offline only, fresh directories required; no overwrite or repair."""
    control, authority_dir, witness_dir = paths(root)
    require(not any(p.exists() or p.is_symlink() for p in (control, authority_dir, witness_dir)))
    control.mkdir(mode=0o700)
    exclusive_file(control / 'maintenance.lock')
    with maintenance_lock(control):
        authority_dir.mkdir(mode=0o700)
        witness_dir.mkdir(mode=0o700)
        authority, witness = authority_dir / 'authority.db', witness_dir / 'witness.db'
        exclusive_file(authority)
        exclusive_file(witness)
        token = secrets.token_hex(32)
        with closing(open_existing(authority)) as db, closing(open_existing(witness)) as guard:
            initialize(db)
            provision(db, SCOPE, token)
            provision_witness(db, guard)
        exclusive_file(control / 'collector.token', (token + '\n').encode())


@contextmanager
def activation(root):
    """Hold the cooperative local maintenance lock for the GAMMA lifetime."""
    control, authority_dir, witness_dir = paths(root)
    for directory in (control, authority_dir, witness_dir):
        private_dir(directory)
    authority, witness = authority_dir / 'authority.db', witness_dir / 'witness.db'
    identities = {p: private_file(p) for p in (authority, witness)}
    require(identities[authority] != identities[witness])
    token_path = control / 'collector.token'
    with maintenance_lock(control) as permitted:
        private_file(token_path)
        token = token_path.read_text().strip()

        def restore_permitted():
            try:
                return permitted() and all(private_file(p) == i for p, i in identities.items())
            except (OSError, ValueError):
                return False

        @contextmanager
        def connect(path):
            require(restore_permitted())
            with closing(open_existing(path)) as db:
                require(restore_permitted())
                db.execute('PRAGMA synchronous=FULL')
                yield db

        with connect(authority) as db, connect(witness) as guard:
            distinct(db, guard)
            row = db.execute('SELECT generation FROM collector_fence WHERE scope=?', ('/'.join(SCOPE),)).fetchone()
            require(row is not None)
            authenticated(db, SCOPE, token, row[0])
            require(guard.execute('SELECT state,digest,lease FROM guard WHERE id=1').fetchone()
                    == ('READY', snapshot(db), None))
        yield {'scope': SCOPE, 'authority': lambda: connect(authority),
               'witness': lambda: connect(witness), 'restore_permitted': restore_permitted}
