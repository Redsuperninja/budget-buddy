"""Errors from the encryption layer. Messages are plain English and never include secrets."""


class EncryptionError(RuntimeError):
    """Base class for encryption problems."""


class KeyStoreError(EncryptionError):
    """The place the master key is kept (the OS password vault) couldn't be used."""


class MissingKeyError(EncryptionError):
    """There is encrypted data in the folder, but no key for it on this computer."""


class WrongKeyError(EncryptionError):
    """The key on this computer doesn't match the data in the folder."""


class DecryptionError(EncryptionError):
    """Data couldn't be decrypted: wrong key, wrong place, or it was changed or damaged."""


class FileTooLargeError(EncryptionError):
    """A file is bigger than the allowed size."""


class RecoveryPhraseError(EncryptionError):
    """A recovery phrase couldn't be read (usually a typo)."""
