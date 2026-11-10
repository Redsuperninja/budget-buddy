"""Errors from the encryption layer. Messages are plain English and never include secrets."""


class EncryptionError(RuntimeError):
    """Base class for encryption problems."""


class KeyStoreError(EncryptionError):
    """The place the master key is kept (the OS password vault) couldn't be used."""


class MissingKeyError(EncryptionError):
    """There is encrypted data in the folder, but no key for it on this computer."""


class WrongKeyError(EncryptionError):
    """The key on this computer doesn't match the data in the folder."""


class KeyCheckError(EncryptionError):
    """The database couldn't be read to check that a key belongs to it."""


class DecryptionError(EncryptionError):
    """Data couldn't be decrypted: wrong key, wrong place, or it was changed or damaged."""


class FileTooLargeError(EncryptionError):
    """A file is bigger than the allowed size."""


class RecoveryPhraseError(EncryptionError):
    """A recovery phrase couldn't be read (usually a typo)."""


class CipherProviderError(EncryptionError):
    """The OpenSSL inside the database encryption library is older than we allow."""


class UnencryptedDatabaseError(EncryptionError):
    """The database file is plain SQLite but encryption is on ."""


BUSY_MESSAGE = (
    "Budget Buddy's database is in use by another copy of Budget Buddy. Close it and try again. "
    "Your data is safe and unchanged."
)
CORRUPT_MESSAGE = (
    "Budget Buddy's database looks damaged, so it stopped before changing anything. Restore "
    "your latest backup, or ask for help."
)


class DatabaseBusyError(EncryptionError):
    """The encrypted database is locked by another process (not a wrong key)."""


class DatabaseCorruptError(EncryptionError):
    """The encrypted database opened with the right key but is damaged (not a wrong key)."""


MOVE_FAILED_MESSAGE = (
    "Budget Buddy couldn't move its database into the encrypted form, so it stopped before "
    "changing your data. Your data is safe and unchanged. Close any other copy of Budget Buddy "
    "and start it again, or ask for help."
)


class DatabaseMoveError(EncryptionError):
    """An existing plain database couldn't be moved into an encrypted file (it is untouched)."""
