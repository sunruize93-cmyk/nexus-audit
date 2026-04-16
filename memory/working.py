"""工作记忆 — 当前批次交易数据的实时缓存

类比人类审计师的"桌面": 正在审查的这一批交易文件。
批次结束后清空, 不跨批次保留。
"""

from __future__ import annotations

from typing import Any

from models import CleanTransaction, SuspiciousTransaction


class WorkingMemory:
    """基于字典的工作记忆, 生命周期 = 单次管道运行"""

    def __init__(self) -> None:
        self._transactions: dict[str, CleanTransaction] = {}
        self._suspicious: dict[str, SuspiciousTransaction] = {}
        self._metadata: dict[str, Any] = {}

    def store_transaction(self, txn: CleanTransaction) -> None:
        self._transactions[txn.invoice_no] = txn

    def store_suspicious(self, sus: SuspiciousTransaction) -> None:
        self._suspicious[sus.transaction.invoice_no] = sus

    def get_transaction(self, invoice_no: str) -> CleanTransaction | None:
        return self._transactions.get(invoice_no)

    def get_all_transactions(self) -> list[CleanTransaction]:
        return list(self._transactions.values())

    def get_all_suspicious(self) -> list[SuspiciousTransaction]:
        return list(self._suspicious.values())

    def set_meta(self, key: str, value: Any) -> None:
        self._metadata[key] = value

    def get_meta(self, key: str, default: Any = None) -> Any:
        return self._metadata.get(key, default)

    def clear(self) -> None:
        self._transactions.clear()
        self._suspicious.clear()
        self._metadata.clear()

    @property
    def transaction_count(self) -> int:
        return len(self._transactions)

    @property
    def suspicious_count(self) -> int:
        return len(self._suspicious)
