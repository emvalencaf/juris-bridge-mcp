"""The CNJ number (`NNNNNNN-DD.AAAA.J.TR.OOOO`): parsing, check digit and Court derivation."""

import re
from dataclasses import dataclass

from juris_bridge_mcp.domain.courts import UFS, stf_not_covered
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

_FORMATTED = re.compile(r"^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$")
_DIGITS = re.compile(r"^\d{20}$")


def _invalid(message: str) -> ToolFailure:
    return ToolFailure(
        ErrorCode.INVALID_ARGUMENT,
        message,
        source=None,
        retryable=False,
        hint="Pass NNNNNNN-DD.AAAA.J.TR.OOOO or the same 20 digits.",
    )


@dataclass(frozen=True)
class CnjNumber:
    """A valid CNJ number, held as its 20 digits."""

    digits: str

    @classmethod
    def parse(cls, raw: str) -> "CnjNumber":
        """Accept the formatted or the 20-digit form; reject a wrong length or check digit."""
        text = raw.strip()
        matched = _FORMATTED.match(text)
        digits = "".join(matched.groups()) if matched else text
        if not _DIGITS.match(digits):
            raise _invalid("A CNJ number has 20 digits, formatted as NNNNNNN-DD.AAAA.J.TR.OOOO.")
        number = cls(digits)
        if int(digits[:7] + digits[9:] + digits[7:9]) % 97 != 1:
            raise _invalid("The CNJ number has a wrong check digit.")
        return number

    @property
    def formatted(self) -> str:
        """Return `NNNNNNN-DD.AAAA.J.TR.OOOO`."""
        d = self.digits
        return f"{d[:7]}-{d[7:9]}.{d[9:13]}.{d[13]}.{d[14:16]}.{d[16:]}"

    @property
    def segment(self) -> int:
        """The `J` digit: which branch of the judiciary."""
        return int(self.digits[13])

    @property
    def tribunal(self) -> int:
        """The `TR` segment: which court within the branch."""
        return int(self.digits[14:16])


_MILITARY_STATE = {13: "tjmmg", 21: "tjmrs", 26: "tjmsp"}


def derive_court(number: CnjNumber) -> str:
    """Map the `J.TR` segments to a Court alias (TRF, TRT, TRE, TJ, TJM; `J=7` is `stm`)."""
    j, tr = number.segment, number.tribunal
    alias: str | None = None
    if j == 1:
        raise stf_not_covered()
    if j == 4 and 1 <= tr <= 6:
        alias = f"trf{tr}"
    elif j == 5 and 1 <= tr <= 24:
        alias = f"trt{tr}"
    elif j == 6 and 1 <= tr <= len(UFS):
        alias = f"tre-{UFS[tr - 1]}"
    elif j == 7 and tr == 0:
        alias = "stm"
    elif j == 8 and 1 <= tr <= len(UFS):
        uf = UFS[tr - 1]
        alias = "tjdft" if uf == "df" else f"tj{uf}"
    elif j == 9:
        alias = _MILITARY_STATE.get(tr)
    if alias is None:
        raise ToolFailure(
            ErrorCode.INVALID_ARGUMENT,
            f"The Court cannot be derived from segments J={j}, TR={tr:02d}.",
            source=None,
            retryable=False,
            hint="Pass the court argument (an alias such as tjsp or stj).",
        )
    return alias
