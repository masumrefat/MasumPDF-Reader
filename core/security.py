"""Encryption / password handling for PDFs."""

import pypdf


class SecurityManager:
    """Add or remove password protection on a PDF."""

    @staticmethod
    def encrypt(input_path: str, output_path: str, user_password: str,
                owner_password: str | None = None,
                allow_print: bool = True, allow_copy: bool = True,
                allow_modify: bool = False):
        """Save an encrypted copy. pypdf handles AES-256 by default in modern versions."""
        reader = pypdf.PdfReader(input_path)
        writer = pypdf.PdfWriter(clone_from=reader)

        permissions = pypdf.PageObject  # placeholder so static analysers don't complain
        # pypdf 4+ API: writer.encrypt(user_password=..., owner_password=...,
        #                              permissions_flag=...)
        try:
            from pypdf.constants import UserAccessPermissions as Perm
            flag = 0
            if allow_print:
                flag |= Perm.PRINT
            if allow_copy:
                flag |= Perm.EXTRACT
            if allow_modify:
                flag |= Perm.MODIFY
            writer.encrypt(
                user_password=user_password,
                owner_password=owner_password or user_password,
                permissions_flag=flag,
                algorithm="AES-256",
            )
        except Exception:
            # fall back to the simple form
            writer.encrypt(user_password=user_password,
                           owner_password=owner_password or user_password)

        with open(output_path, "wb") as f:
            writer.write(f)

    @staticmethod
    def decrypt(input_path: str, output_path: str, password: str) -> bool:
        """Save a copy without password. Returns True on success."""
        reader = pypdf.PdfReader(input_path)
        if reader.is_encrypted:
            ok = reader.decrypt(password)
            if not ok:
                return False
        writer = pypdf.PdfWriter(clone_from=reader)
        with open(output_path, "wb") as f:
            writer.write(f)
        return True

    @staticmethod
    def permissions(path: str) -> dict:
        """Best-effort report of permissions on an encrypted PDF."""
        reader = pypdf.PdfReader(path)
        if not reader.is_encrypted:
            return {"encrypted": False}
        info = {"encrypted": True}
        try:
            from pypdf.constants import UserAccessPermissions as Perm
            perms = reader.user_access_permissions
            if perms is not None:
                info.update({
                    "print": bool(perms & Perm.PRINT),
                    "modify": bool(perms & Perm.MODIFY),
                    "extract": bool(perms & Perm.EXTRACT),
                    "fill_forms": bool(perms & Perm.FILL_FORM_FIELDS),
                })
        except Exception:
            pass
        return info
